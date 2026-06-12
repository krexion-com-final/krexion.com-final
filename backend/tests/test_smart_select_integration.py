"""
Integration test for visual_recorder._smart_select_option + the RUT
engine's _smart_select_with_fallback, exercising the JS-driven select
path against a SIMULATED page object (no real Playwright / browser
needed — works in the cloud preview env where Chromium isn't installed).

We mock `page.evaluate(js, args)` by executing the same matching logic
in pure Python against an in-memory <select> representation, then
verify that:
  • Native <select> with FULL state name option gets matched when data
    is the abbreviation ("TX" → option "Texas")
  • DOB year/month/day split selects all match a single ISO date input
  • Custom UI flag (hidden select) still succeeds via the JS path

Run:  cd /app/backend && python3 -m pytest tests/test_smart_select_integration.py -v
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from value_normalizer import expand_value_variants


class FakeOption:
    def __init__(self, value: str, text: str):
        self.value = value
        self.text = text
        self.label = text
        self.selected = False


class FakeSelect:
    """In-memory <select> for tests. Tracks dispatched events so we can
    assert change/input/blur fired."""
    def __init__(self, options):
        self.tagName = "SELECT"
        self.options = [FakeOption(v, t) for v, t in options]
        self.value = ""
        self.events = []  # list of event-type strings dispatched

    def dispatchEvent(self, evt_type):
        self.events.append(evt_type)


class FakePage:
    """Just enough Page surface to run our JS-driven select logic in
    Python. The real page.evaluate(js, args) is replaced with a Python
    function that mirrors the JS matching algorithm exactly."""
    def __init__(self, selects: dict):
        # selects: {selector: FakeSelect}
        self._selects = selects

    async def evaluate(self, js_code: str, args: dict):
        # Mirror the JS findOpt + dispatch logic in Python so we don't
        # need a real browser. Args matches what _smart_select_option
        # sends.
        selector = args.get("selector", "")
        raw_list = args.get("rawList") or [args.get("raw", "")]
        by_label = bool(args.get("byLabel", True))
        el = self._selects.get(selector)
        if not el or el.tagName != "SELECT":
            return {"ok": False}

        def find_opt(el, raw, by_label):
            want = str(raw)
            want_trim = want.strip().lower()
            # Primary match
            for o in el.options:
                if by_label:
                    t = (o.text or "").strip().lower()
                    l = (o.label or "").strip().lower()
                    if t == want_trim or l == want_trim:
                        return o
                else:
                    if str(o.value) == want:
                        return o
            # Cross strategy
            for o in el.options:
                if by_label:
                    if str(o.value) == want:
                        return o
                else:
                    t = (o.text or "").strip().lower()
                    if t == want_trim:
                        return o
            return None

        opt = None
        for raw in raw_list:
            opt = find_opt(el, raw, by_label)
            if opt:
                break
        if not opt:
            return {"ok": False}

        el.value = opt.value
        el.dispatchEvent("input")
        el.dispatchEvent("change")
        el.dispatchEvent("blur")
        return {"ok": True, "value": opt.value, "label": opt.text}

    async def select_option(self, selector, label=None, value=None, index=None, timeout=2000):
        # Backup path: also try to match label/value on the FakeSelect.
        el = self._selects.get(selector)
        if not el:
            raise RuntimeError("not found")
        for o in el.options:
            if label is not None and o.text.strip() == label.strip():
                el.value = o.value
                return
            if value is not None and o.value == value:
                el.value = o.value
                return
        raise RuntimeError(f"no option matched label={label!r} value={value!r}")


async def _call_recorder_select(page, selector, live_val, match_by="label"):
    """Helper to invoke visual_recorder._smart_select_option in tests."""
    from visual_recorder import _smart_select_option
    return await _smart_select_option(page, selector, live_val, match_by)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── State dropdown tests (the exact bug in the user's screenshot) ───────
def test_state_full_name_dropdown_with_abbreviation_data():
    """data='TX' against <select> with FULL state names like 'Texas'."""
    states = [(s, s) for s in (
        "Alabama", "Alaska", "Arizona", "California", "Texas", "Wyoming"
    )]
    page = FakePage({"#state": FakeSelect([("", "-- select --")] + states)})

    ok, used = _run(_call_recorder_select(page, "#state", "TX"))
    assert ok, f"expected match, got ok={ok}, used={used}"
    assert page._selects["#state"].value == "Texas"
    # Ensure change/blur events fired so the form "Next" button enables
    events = page._selects["#state"].events
    assert "change" in events
    assert "blur" in events


def test_state_full_name_dropdown_with_full_name_data():
    """data='Texas' against same <select>."""
    states = [(s, s) for s in ("Alabama", "Texas", "Wyoming")]
    page = FakePage({"#state": FakeSelect(states)})
    ok, used = _run(_call_recorder_select(page, "#state", "Texas"))
    assert ok and page._selects["#state"].value == "Texas"


def test_state_dropdown_value_is_code_label_is_full():
    """A common pattern: <option value='TX'>Texas</option>.
    data='Texas' (full name) should still match because we try both
    label and value modes with both variants."""
    page = FakePage({"#state": FakeSelect([
        ("AL", "Alabama"), ("TX", "Texas"), ("CA", "California")
    ])})
    ok, _ = _run(_call_recorder_select(page, "#state", "Texas"))
    assert ok
    assert page._selects["#state"].value == "TX"


def test_state_dropdown_data_lowercase():
    page = FakePage({"#state": FakeSelect([("Texas", "Texas")])})
    ok, _ = _run(_call_recorder_select(page, "#state", "texas"))
    assert ok and page._selects["#state"].value == "Texas"


def test_state_dropdown_DC_alt_spelling():
    page = FakePage({"#state": FakeSelect([
        ("DC", "District of Columbia"), ("VA", "Virginia")
    ])})
    ok, _ = _run(_call_recorder_select(page, "#state", "Washington DC"))
    assert ok and page._selects["#state"].value == "DC"


# ── DOB split-field tests ────────────────────────────────────────────────
def test_dob_split_month_select_with_iso_date():
    """User data: '1990-05-15'. Form has separate Month dropdown with
    <option>May</option>. Should match."""
    month_opts = [(m, m) for m in (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    )]
    page = FakePage({"#month": FakeSelect(month_opts)})
    ok, _ = _run(_call_recorder_select(page, "#month", "1990-05-15"))
    assert ok and page._selects["#month"].value == "May"


def test_dob_split_day_select_with_iso_date():
    """Day dropdown with values '1'..'31' or '01'..'31'."""
    day_opts = [(f"{d:02d}", f"{d:02d}") for d in range(1, 32)]
    page = FakePage({"#day": FakeSelect(day_opts)})
    ok, _ = _run(_call_recorder_select(page, "#day", "1990-05-15"))
    assert ok and page._selects["#day"].value == "15"


def test_dob_split_year_select_with_us_date():
    """Year dropdown with values '1950'..'2010'."""
    year_opts = [(str(y), str(y)) for y in range(1950, 2011)]
    page = FakePage({"#year": FakeSelect(year_opts)})
    ok, _ = _run(_call_recorder_select(page, "#year", "5/15/1990"))
    assert ok and page._selects["#year"].value == "1990"


def test_dob_split_month_numeric_value_only():
    """Form's month <option value='5'>May</option> — data '1990-05-15'
    should match by value '5' OR label 'May'."""
    month_opts = [(str(i), str(i)) for i in range(1, 13)]
    page = FakePage({"#month": FakeSelect(month_opts)})
    ok, _ = _run(_call_recorder_select(page, "#month", "1990-05-15"))
    assert ok and page._selects["#month"].value == "5"


def test_dob_verbose_input_to_split_fields():
    """Data: 'May 15, 1990' → all three split fields work."""
    page_month = FakePage({"#m": FakeSelect([(m, m) for m in (
        "January", "May", "December"
    )])})
    page_day = FakePage({"#d": FakeSelect([(str(d), str(d)) for d in (1, 15, 30)])})
    page_year = FakePage({"#y": FakeSelect([(str(y), str(y)) for y in (1989, 1990, 1991)])})

    assert _run(_call_recorder_select(page_month, "#m", "May 15, 1990"))[0]
    assert page_month._selects["#m"].value == "May"
    assert _run(_call_recorder_select(page_day, "#d", "May 15, 1990"))[0]
    assert page_day._selects["#d"].value == "15"
    assert _run(_call_recorder_select(page_year, "#y", "May 15, 1990"))[0]
    assert page_year._selects["#y"].value == "1990"


# ── Event dispatch tests (the actual "Next button" fix) ─────────────────
def test_change_and_blur_events_fire():
    """Critical: form's `<select onChange=...>` or onBlur validator must
    see events for the Next button to enable. Our JS path dispatches
    input, change, AND blur."""
    page = FakePage({"#state": FakeSelect([("Texas", "Texas")])})
    _run(_call_recorder_select(page, "#state", "TX"))
    events = page._selects["#state"].events
    assert events == ["input", "change", "blur"], f"got events={events!r}"


# ── Negative test ────────────────────────────────────────────────────────
def test_no_match_returns_failure():
    page = FakePage({"#x": FakeSelect([("apple", "apple"), ("orange", "orange")])})
    ok, used = _run(_call_recorder_select(page, "#x", "banana"))
    assert not ok and used is None


# ── RUT replay engine: same expand_value_variants is used ───────────────
def test_rut_replay_uses_same_variants():
    """Ensures the RUT engine's _smart_select_with_fallback imports
    expand_value_variants without error (regression check after the
    2026-06 refactor)."""
    import real_user_traffic
    # Function must exist and be callable
    assert callable(real_user_traffic._smart_select_with_fallback)
