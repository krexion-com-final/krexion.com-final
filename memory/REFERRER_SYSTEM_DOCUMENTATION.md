# Krexion Referrer System — Complete Technical Documentation
_Source of truth: `backend/referrer_pro.py` (2 673 lines), `backend/referrer_pro_api.py` (258 lines), `backend/real_user_traffic.py` (§ 936–1 500, § 7 860–8 640), `frontend/src/pages/RealUserTrafficPage.js`._
_Version at time of writing: **v2.6.7**._

> Har answer actual code se verified hai. Line numbers reference karte hain taake aap khud check kar sakein.

---

## 1. Referrer Generation

### Kya generate karta hai
Referer URL **per-visit** generate hoti hai — ek job ke andar 1 000 visits hain to 1 000 alag referer URLs banti hain (repetition system-level anti-pattern hai; deliberately avoid kiya gaya).

### Static vs Dynamic
**Dynamic — templates + random tokens.** Poori library mein koi bhi hardcoded "static URL" nahi hai. Har URL ek template hai jismein 1–5 random-token placeholders hote hain (line 386–395 of `referrer_pro.py`):

```
{enc_u}     → URL-encoded destination URL       (per-visit)
{tco_id}    → Twitter t.co 10-char base62 ID    (per-visit random)
{lnkd_id}   → LinkedIn lnkd.in 8-char base36    (per-visit random)
{pin_id}    → Pinterest 17-18 digit pin ID      (per-visit random)
{hash16}    → 16 hex chars                       (per-visit random)
{hash32}    → 32 hex chars                       (per-visit random)
{yt_vid}    → 11-char base64url YouTube ID       (per-visit random)
{yt_channel}→ 4-20 char @handle                  (per-visit random)
```

Plus platform-specific realism suffixes (line 397–431):
- Facebook `l.facebook.com/l.php` → real `h=AT<58-104-char>` hash + `__cft__[0]=AZ<80-200-char>` token in 75% of visits + `__tn__` param in 50% + `_lp=1` in 10%. Ye distributions actual real Meta linkshim sampling se aayin hain (comment line 322–336).
- Facebook `pfbid<49-char>` post token (line 545–548) — modern 2026 format
- TikTok video URL: `/@user<6-10digits>/video/<19-digit-vid-id>` (line 476–478)
- Instagram post URL: `/p/<11-char-base64url>/` (line 480–481)

### Selection Method
**Weighted-random** primary; **pure-random** for template picks within a platform's pool.

Weighted-random pipeline (`resolve_pro_visit`, line 1 291–1 503):
1. Parse operator's platform weights (`parse_weighted_pool`, line 997)
2. Optionally apply time-of-day multiplier (`_HOUR_WEIGHTS`, line 1 259)
3. Pick one platform (`pick_weighted`, line 1 105)
4. Within that platform's wrapper pool, pick a template (weighted, line 373–381 of `build_social_wrapper_referer`)
5. Fill placeholders with fresh random tokens

---

## 2. HTTP Referer vs `document.referrer`

### HTTP `Referer` header
**Yes** — set at TWO layers:
1. **Playwright `page.goto(url, referer=…)` kwarg** — this is the ONLY reliable way to set the very first navigation's Referer (Chromium NetworkService silently drops `Referer` from `extra_http_headers` on the initial request — comment line 7 871–7 887 of `real_user_traffic.py`; upstream bug: `microsoft/playwright#3597`).
2. **`extra_http_headers={"Referer": ...}`** on the browser context — used for **subsequent** navigations (AJAX → page-change reloads).

Actual code (line 8 584):
```python
resp = await page.goto(_visit_target_url, timeout=35000,
                       wait_until=_wait_until, **_goto_referer_kw)
```
Where `_goto_referer_kw = {"referer": _ua_referer}` (line 7 911–7 913).

### `document.referrer` (JS-side)
**Not actively spoofed** — Playwright ke through set kya Referer header automatically hi `document.referrer` mein reflect ho jaata hai (browser standard behaviour). System ek defensive JS shim inject karta hai (line 4 874–4 891) sirf itna ensure karne ke liye ke `document.referrer === undefined` na ho (rare Chromium edge case) — value change nahi karta.

**Dono ek saath aisay handle hote hain:**
| Layer | What sets it | Consistency |
|---|---|---|
| HTTP `Referer` header (first goto) | `page.goto(..., referer=X)` | Set by Playwright |
| HTTP `Referer` header (subsequent navs) | `extra_http_headers["Referer"] = X` | Set by context |
| `document.referrer` in DOM | Auto-derived by Chromium from HTTP Referer | Consistent by construction |

---

## 3. Navigation Method

**Direct navigation** hai — `page.goto(target_url, referer=<generated_referer>)`.

Ye **redirect chain simulate nahi karta** kyunki uski zaroorat hi nahi:
- Real ad click ka HTTP-level end state = "browser landed on destination page with Referer=<platform>". Ye state Krexion 1 goto call se hi produce kar deta hai.
- **Kya nahi hota:** Meta refresh, JavaScript-side `window.location = ...`, real link-click simulation, iframe hopping.

Optional **Network Click Chain hop** hai (line 7 899–7 908, `real_user_traffic.py`) — jab operator ne `network_click_chain` toggle ON kiya ho:
- Real ad flow: `platform (l.facebook.com) → ad-network click host (sig.click.com / go.linksynergy.com / …) → advertiser landing`
- Krexion ye directly ONE `page.goto` mein deliver karta hai: destination = advertiser landing, **Referer** = ad-network host (nahi ke platform). This is the shortcut — server-side chain skip hai but the final HTTP signature that the offer sees is identical.

**Optional health-check preflight** (`hcResult` in RUT UI, comment line 780–789 of RealUserTrafficPage.js) — dry-run 1 visit on ONE browser BEFORE committing budget to full job. Uses same `page.goto` flow, no separate mechanism.

---

## 4. Referrer Pools — per Platform

Yeh actual pools hain (verbatim from `_SOCIAL_WRAPPER_REFERERS`, line 186–283 of `referrer_pro.py`):

| Platform | Wrapper templates | Notes |
|---|---|---|
| **Facebook** | 5 | l.facebook.com/l.php · lm.facebook.com/l.php · www.facebook.com · m.facebook.com · "" (empty for strict-origin policy) |
| **Instagram** | 4 | l.instagram.com · www.instagram.com · help.instagram.com · "" |
| **TikTok** | 4 | tiktok.com/link/v2 · www.tiktok.com · m.tiktok.com · "" |
| **Twitter/X** | 2 | t.co/{10-char-id} · twitter.com |
| **LinkedIn** | 3 | lnkd.in/{8-char-id} · linkedin.com · linkedin.com/feed |
| **Reddit** | 3 | out.reddit.com · www.reddit.com · old.reddit.com |
| **YouTube** | 6 | www.youtube.com/watch · m.youtube.com/watch · shorts · homepage · m.youtube.com · @channel |
| **Snapchat** | 2 | www.snapchat.com · l.snapchat.com |
| **Pinterest** | 2 | www.pinterest.com · www.pinterest.com/pin/{id}/ |
| **WhatsApp** | 2 | "" (95%) · api.whatsapp.com (5%) |
| **Telegram** | 2 | "" (85%) · t.me (15%) |
| **Discord** | 2 | "" (85%) · discord.com (15%) |

**Plus** in-app deep-path builders (`build_inapp_deep_referer`, line 460–556) generate ADDITIONAL per-visit unique URLs (video IDs, post IDs, story activities) — so effective per-visit-uniqueness for TikTok/Instagram/Facebook = **millions of variations** (random 11–19-char IDs).

**Search engines (49 countries × 8 engines):** `_GEO_SEARCH_HOSTS` (line 52–104) has 49 country entries; `build_search_referer` (line 117) supports **google, bing, yahoo, duckduckgo/ddg, yandex, youtube, baidu, naver** = 8 engines. Total search-referer combinations ≈ 49 × 8 = **392 base hosts** × unlimited keyword variations.

**Email/ESP pool (14 ESPs + 4 webmails):**
- Webmails: `WEBMAIL_REFERERS` (line 1 169) — gmail · outlook · yahoo · proton (4)
- ESP click-tracking hosts: `EXTENDED_ESP_HOSTS` (line 1 142–1 167) — mailchimp (6 hosts) · sendgrid (4) · klaviyo (3) · hubspot (4) · activecampaign (3) · convertkit (3) · constantcontact (3) · mailerlite (3) · brevo (3) · aweber (2) · drip (2) · iterable (2) · marketo (2) · pardot (2) = **42 unique ESP redirector hosts** across **14 ESPs**.

**Native Ads:** No dedicated "native ads" pool. `_NETWORK_CLICK_HOSTS` (line 952–965) has **12 affiliate-network 302 redirector hosts** (trk.affiliatenetwork.com, click.mb01.com, go.linksynergy.com, click.linksynergy.com, tracker.gateway.com, go.maxbcb.com, afftrk.com, tracking.glitchyads.com, track.performcb.com, go.performcb.com, click.networkx.io) which cover the network-click-chain use case.

### Maintenance
**Manually maintained.** Rebalances happen when the developer sees a fraud-signal cluster on real Anura/IPQS/Forensiq dashboards. Every major rebalance is documented inline with the date + reason:
- FB wrapper rebalance (2026-07 v2.2.0, line 186–204)
- FB `h=` hash length bump (2026-06-15, line 322–336)  
- FB `__cft__[0]` token addition (2026-06-15, line 340–352)
- IG `l.instagram.com` de-emphasised (2026-07 v2.2.0, line 205–213)
- YouTube redirect leak fix (2026-07 v2.2.5, line 243–262)

**No auto-update.** UA versions (Facebook FBAV 515.1.0.62.90 etc., line 1 541–1 546) also manually maintained. `POST /api/admin/ua-versions/refresh` DOES auto-refresh Chrome/Firefox versions from Mozilla API but that's UA-only, not referrer URLs.

---

## 5. URL Rotation Strategy

**Weighted-random per visit** — not round-robin, not sticky. Every single `page.goto` call runs the full pick pipeline fresh.

**Weighted random algorithm** (`pick_weighted`, line 1 105–1 118):
```python
total = sum(max(0.0, w) for _, w in pool)
roll = random.random() * total
acc = 0.0
for key, w in pool:
    acc += max(0.0, w)
    if roll <= acc:
        return key
```
Weights **do not have to sum to 100** — they're relative (comment in Customize panel).

**Within each platform's wrapper pool** — also weighted random (line 373–381). E.g. Facebook picks the `l.facebook.com/l.php` template 15% of visits, `lm.facebook.com/l.php` 10%, `www.facebook.com` 45%, `m.facebook.com` 20%, empty 10%.

**Optional layer — Time-of-Day pacing** (`time_of_day_weight`, line 1 271–1 285): 24-hour multiplier table per platform (`_HOUR_WEIGHTS`, line 1 259) multiplies weights before the pick. e.g. TikTok evening spike (hours 19–20 → 1.8–2.0x), LinkedIn business hours (hours 9–11 → 1.7–1.8x). Only active when `tod_enabled=True` in the pro-mode resolver.

**No Sticky Session:** Sticky is deliberately avoided — real bulk affiliate traffic doesn't have session persistence across visits. Anti-fraud vendors (Anura, IPQS) flag repeated-referer clusters as bot signal.

**No Round-Robin / Sequential:** Not implemented. Would produce a mathematically-perfect distribution which is itself a bot tell.

---

## 6. Presets — Exact Configuration

Presets are defined in `RealUserTrafficPage.js` lines 726–774 (the effect that watches `trafficSourcePreset`). **Every preset switches ~10 internal toggles**:

### Common defaults (every non-off preset)
```
refererOverrideEnabled     = true
refererPassToOffer         = true
refererMatchUaToPlatform   = true
refererProMode             = true
refererMode                = "platform_pool"
refererSocialWrapper       = true
refererInappDeep           = true
refererStripSearchPath     = true
inappBrowserPreset         = "none"   (let UA rotate per visit)
refererValue               = ""       (preset owns the source)
```

### Per-preset overrides
| Preset | Platform Weights | Realism toggles that differ from defaults |
|---|---|---|
| **⭐ mixed_realistic** | fb:30, ig:15, tt:20, google:20, twitter:5, email:10 | `networkClickChain=true`, `searchEngine="google"` |
| **📱 social_media_ads** | fb:40, ig:30, tt:25, twitter:5 | `networkClickChain=true`, `searchEngine="google"` |
| **🔍 search_engine_ads** | google:65, bing:25, ddg:5, yandex:5 | `networkClickChain=false`, `inappDeep=false`, `socialWrapper=false` |
| **📧 email_campaign** | email:100 | `emailWeights={gmail:40, outlook:20, yahoo:10, mailchimp:15, klaviyo:10, empty:5}`, `networkClickChain=false`, `inappDeep=false`, `socialWrapper=false` |
| **🎯 direct_traffic** | (ignored) | `refererMode="direct"`, `proMode=false`, `networkClickChain=false`, `socialWrapper=false`, `inappDeep=false`, `passToOffer=true` (keeps blank-Referer via BUG #9 fix) |
| **⚙️ custom** | (no auto-config) | 20+ manual toggles visible |
| **🚫 off** | (n/a) | `refererOverrideEnabled=false`, all toggles preserved from previous state |

Preset effect is idempotent — flipping between presets always produces a clean, conflict-free state.

---

## 7. Custom Mode — Full Controllable Fields

Custom mode exposes **every** underlying resolver knob. Complete list from `RealUserTrafficPage.js`:

**Master switches:**
- `refererOverrideEnabled` (bool)
- `refererMode` — `auto | platform_pool | custom | random_list | google_search | direct`
- `refererProMode` (bool — enables weighted pools + all realism layers)

**Pool / weights:**
- `refererPlatformPool` (comma-list, legacy)
- `refererPlatformWeights` (JSON object per platform, pro-mode)
- `refererEmailWeights` (JSON object per ESP/webmail, pro-mode)

**Single URLs:**
- `refererValue` (for mode=custom / random_list / google_search)
- `refererBrand` (per-visit UTM brand tag)

**Search:**
- `refererSearchEngine` — `google | bing | yahoo | duckduckgo | ddg | yandex | youtube | baidu | naver`
- `refererSearchKeywords` (newline-separated pool)
- `refererStripSearchPath` (bool — origin-only vs full `/search?q=`)

**Realism layers:**
- `refererSocialWrapper` (bool — l.facebook.com, t.co, lnkd.in, out.reddit.com wrappers)
- `refererInappDeep` (bool — deep video/post/story URLs)
- `refererNetworkClickChain` (bool + optional network host override)
- `refererPassToOffer` (bool — bypass tracker origin leak)
- `refererMatchUaToPlatform` (bool — UA coercion to add FBAN/FBAV/musical_ly/Instagram in-app markers)

**Country / language:**
- `country` (ISO-2, drives geo-search hosts + Accept-Language)
- `lang_match` (bool — sets country-matched Accept-Language)

**Device:**
- `device_mode` — `auto | match_platform | mobile_only | desktop_only`

**Time-of-day:**
- `tod_enabled` (bool)

**Campaign presets (UTM):**
- `campaign_type` — `auto | prospecting | remarketing | retargeting | lookalike | native | discovery | brand | performance` (line 2 425)

**Quality tier:**
- `quality_tier` — `basic | standard | premium | enterprise` (line 2 477)

Total = **~22 independent knobs.** Custom mode = "show every toggle."

---

## 8. Validation Rules

**Explicit validation is minimal by design.** The resolver is built to be forgiving — malformed input never blocks a job; falls back to a legacy path silently. Actual validations:

| Check | Where | Behaviour |
|---|---|---|
| Invalid platform key (e.g. "tikktok") | `parse_weighted_pool` line 1 087 | Silently dropped from pool |
| All-zero weights on valid keys | `parse_weighted_pool` Bug #8 fix, line 1 054–1 063 | Falls back to equal-weight (does NOT drop pool) |
| Empty pool after parsing | `resolve_pro_visit` line 1 355 | Returns empty referer (no crash) |
| Empty search keywords | `build_search_referer` line 131 | Uses `strip_path=True` (origin-only URL) |
| Unknown search engine | `build_search_referer` line 172–176 | Falls back to `google` with country host |
| Malformed JSON in `platform_weights` | `parse_weighted_pool` line 1 067 | Falls through to comma-list parser |
| Empty referer_value in `custom` mode | `_resolve_visit_referer` line 1 238 | Uses UA-derived referer (legacy fallback) |
| Empty referer_value in `random_list` | line 1 258 | Falls back to UA-derived |
| Unknown referer_mode | line 1 361 | Falls back to UA-derived |
| Duplicate name (SAVED PRESET) | `traffic_source_presets_module.py` line 100 | Returns HTTP 409 with clear message |

**What is NOT validated (deliberate design choice):**
- ❌ "Facebook + Google together" — this is a VALID mix (mixed_realistic preset uses it)
- ❌ "Direct Traffic + Social Wrapper" — the preset system already turns off social_wrapper when direct is picked (line 771), but manual combining is allowed
- ❌ Invalid URL format (e.g. `hxxp://…`) — Playwright will reject at nav time
- ❌ Broken URLs (404, DNS fail) — not checked pre-flight; visit fails at nav time with logged reason
- ❌ Duplicate URLs in `random_list` — kept as-is (increases weight of that URL by presence)

Design rationale (comment line 1 011–1 013): _"All modes are PURE-PYTHON and never raise — any malformed cfg silently falls back to legacy auto-from-UA behaviour so an operator typo can never break a live campaign."_

---

## 9. URL Management

| Feature | Status | Where |
|---|---|---|
| Duplicate URL removal | ❌ Not automatic | random_list keeps duplicates on purpose (weighted-by-count) |
| Invalid URL detection | ❌ Not pre-flight | Playwright throws at nav time; error logged per visit |
| Broken URL detection | ❌ Not pre-flight | Optional Health-Check preflight (1-visit dry run) available for that |
| Platform auto-detection | ✅ Yes | `_platform_from_referer_url` (line 1 416+) maps host substrings → platform for consistent downstream UA coercion + UTM tagging |
| Import (JSON) | ✅ Yes | `platform_weights` accepts JSON dict or array (line 997) |
| Export | ❌ No dedicated export | Saved presets are the effective export mechanism (v2.6.7+) |

Platform auto-detection order (host-substring match, `_platform_from_referer_url`):
1. Email marketing hosts (checked FIRST so `mailchi.mp`, `list-manage.com`, `trk.klaviyomail.com` etc. get email tag)
2. Social/search referers (facebook.com, tiktok.com, google.com, …)

---

## 10. Country Awareness

**YES — full 49-country coverage.** `_GEO_SEARCH_HOSTS` (line 52–104) maps ISO-2 → per-engine geo-localised hosts.

Examples:
| Country | Google | Bing (cc param) | Yahoo |
|---|---|---|---|
| US | www.google.com | US | search.yahoo.com |
| DE | www.google.de | DE | de.search.yahoo.com |
| GB | www.google.co.uk | GB | uk.search.yahoo.com |
| PK | www.google.com.pk | PK | search.yahoo.com |
| JP | www.google.co.jp | JP | search.yahoo.co.jp |

**What DOES change by country:**
- ✅ Google TLD (google.com → google.de/co.uk/co.in/…)
- ✅ Bing regional `cc=<CC>` param
- ✅ Yahoo regional subdomain
- ✅ Accept-Language header (via `accept_language_for_country`, line 2 343 when `lang_match=True`)

**What does NOT change automatically:**
- ❌ Facebook regional versions (fb.com works globally with `Accept-Language` for locale)
- ❌ Instagram regional versions (single global instagram.com)
- ❌ TikTok regional (single global tiktok.com)
- ❌ Localised social wrapper URLs (Krexion uses `.com` variants)

Rationale: Social platforms (FB/IG/TikTok) run a single global domain and rely on `Accept-Language` + IP-geo for localisation — matches real 2026 architecture.

---

## 11. Mobile vs Desktop

**Yes — separate pools + device-filter logic.**

**Two mechanisms:**

### A) In-app deep path filter (line 1 458–1 464)
```python
if inapp_deep_path_enabled:
    inapp_kind = is_inapp_browser_ua(ua)   # returns "tiktok"|"facebook"|... if UA contains marker
    if inapp_kind == signal:
        # use full deep-path URL (video/post/story)
```
Only fires when the UA IS an in-app webview (e.g. contains `musical_ly`, `FBAN/`, `Instagram`). Plain Chrome/Safari UAs skip deep paths → get wrapper URLs instead.

### B) Explicit device_mode filter (line 1 358–1 368)
- `match_platform` — filters pool to platforms that match visitor's device (`platform_matches_device`, line 2 391)
- `mobile_only` — drops desktop-leaning platforms (LinkedIn keeps, but LinkedIn desktop is dominant)
- `desktop_only` — drops mobile-only platforms (TikTok, Snapchat, Instagram feed are mobile-first)

Platform-device expectation table (`platform_device_expectation`, line 2 386):
- **Mobile-only:** tiktok, snapchat, instagram (in-app)
- **Desktop-leaning:** linkedin, reddit (partly)
- **Balanced:** facebook, twitter, youtube, google, bing, email

Different social **wrapper pools per platform** don't split mobile/desktop — but `m.facebook.com` vs `www.facebook.com` variants in the FB pool implicitly cover both. TikTok pool has `m.tiktok.com` separately.

---

## 12. Referrer Preview (pre-launch)

**Yes** — two mechanisms:

### A) UI-side preview
`RealUserTrafficPage.js` lines 3 461–3 501 render an "✓ Auto-configured settings for this preset" summary box **live** as the operator picks/changes preset. Shows the exact platform mix + realism toggles that will apply.

### B) Backend dry-run endpoint
`POST /api/referrer-pro/test-resolve` (`referrer_pro_api.py`, line 225–257). Accepts operator's config, returns **N (1–50) sample resolutions** with actual generated Referer URLs. Frontend can call this to render "here are 10 example Referer URLs the resolver would emit."

Example request:
```json
{
  "ua": "Mozilla/5.0 ... TikTok/26.5.0",
  "platform_weights": "{\"tiktok\": 100}",
  "target_url": "https://mypromo.com/offer",
  "country": "us",
  "samples": 10
}
```
Returns 10 unique generated referers so operator can preview.

Additionally: **Health Check** (`hcResult` state) runs an actual 1-visit end-to-end preflight on ONE browser using the full config — captures real headers, DOM state, timing per step.

---

## 13. Platform Distribution — Fixed vs User

**Both — user-configurable per preset.**

- **Preset defaults** are fixed values (see § 6 table).
- **Custom + Customize This Preset panel** (v2.6.7) let user override ANY platform's weight via inline % input.
- **No enforced min/max** — the input accepts 0–100 (client-side clamp, `parseInt` with `Math.max(0, Math.min(100, …))`). Actual internal handling: weights **do not have to sum to 100**; they're relative — `pick_weighted` normalises by dividing by total.
- **Zero-out to disable** — setting a platform's weight to 0 excludes it from the pool (safety fallback: if ALL weights are 0 BUT the JSON had valid platform keys, equal weight applied — Bug #8 fix line 1 054).

---

## 14. Redirect Chain

**Single-hop by default, optional 2-hop via Network Click Chain.**

Default (Chain OFF):
```
[proxied browser] --page.goto(offer_url, referer=platform_referer)--> [offer landing]
```

Network Click Chain ON (`network_click_chain_enabled=True`):
```
Referer that OFFER sees = ad-network host (e.g. sig.click.com/click.php?aff=…)
```
The chain is **synthesised** into the Referer header rather than actually performing the intermediate hop. From the advertiser's HTTP-server-log perspective this is indistinguishable from a real 302-redirect chain, because the advertiser only sees the FINAL request.

Full 3-hop `Facebook → Google → Landing` chain: **NOT supported** — no real user flow produces this. Real chains are:
- `Platform → Ad Network → Landing` (Krexion supports this via Network Click Chain)
- `Search Engine → Landing` (Krexion via search-engine referer)
- `Email → Landing` (Krexion via ESP click-tracking referer)

`Pass-Referer-To-Offer` (line 606–686) additionally rewrites the wrapped `u=`/`url=` param in the Referer so it points to the FINAL offer URL, not the intermediate tracker — closes the "krexion.com origin leak" that used to appear in `l.facebook.com/l.php?u=https%3A%2F%2Fkrexion.com%2Ft%2Fxyz`.

---

## 15. Logging

Per-visit logging (goes into the RUT job document + live activity stream):

| Field | Where stored |
|---|---|
| Generated Referer URL | `push_live_step(job_id, i+1, "referer", "info", …)` (line 7 905) |
| Selected platform signal | Same push_live_step + job doc |
| ESP (if email) | Same |
| UA used (potentially coerced) | Same |
| Proxy exit country/IP | Persisted to `rut_burnt_ips` collection (line 5 061, 5 244) |
| Sec-Fetch headers | Applied to context, not separately logged |
| UTM source/medium/campaign | Emitted into URL params (visible in offer's URL) |

**Not stored:**
- ❌ "Last generated referrer" cache across jobs
- ❌ Rotation history / round-robin cursor (system is stateless-random)
- ❌ Campaign-level referer history dashboard (individual job docs contain per-visit trail; no aggregate view)

**Live-activity streaming** (used by RUT UI's "Live Activity" panel + "Visual Recorder" grid) does show per-visit generated Referer in real time — but this is ephemeral (kept ~24h in job doc).

---

## 16. API / Extensibility

**Modular by design.** New platforms can be added in **3 files** without touching resolver logic:

1. **`referrer_pro.py`:**
   - Add key to `VALID_PLATFORM_KEYS` (line 989)
   - Add wrapper templates to `_SOCIAL_WRAPPER_REFERERS` (line 186)
   - Optionally add deep-path builder branch to `build_inapp_deep_referer` (line 460)
   - Optionally add UTM variations to `_UTM_VARIATIONS` (line 722)
   - Optionally add campaign name templates to `_UTM_CAMPAIGN_TEMPLATES` (line 809)

2. **`real_user_traffic.py`:**
   - Add UA marker → referer mapping to `_UA_REFERER_MAP` (line 936) for in-app detection
   - Add homepage URL to `_PLATFORM_REFERER_POOL` (line 1 015)

3. **`RealUserTrafficPage.js`:** Add option to any preset's default weights (optional).

Backend has NO hardcoded platform list in resolver logic — everything goes through the `VALID_PLATFORM_KEYS` set. `parse_weighted_pool` accepts anything in that set.

**Extension points already leveraged for:** email (added as pseudo-platform), search engines (google/bing/yahoo/ddg/yandex — technically same code path as social), YouTube (added as separate platform mid-2026).

---

## 17. Hidden / Internally-Used Features

Features present in the code but not exposed in the UI (as of v2.6.7):

| Feature | Line ref | Status |
|---|---|---|
| `campaign_type` presets (prospecting/remarketing/lookalike/…) | 2 425–2 465 | Not exposed in RUT UI; used internally when set programmatically via API |
| `quality_tier` (basic/standard/premium/enterprise) | 2 477–2 490 | Same — internal-only |
| `tod_enabled` (time-of-day weighting) | 1 373–1 383 | Not exposed in UI, only via API |
| `device_mode: mobile_only/desktop_only/match_platform` | 1 360–1 368 | Not exposed |
| `lang_match` (auto Accept-Language from country) | 1 342–1 343 | Not exposed |
| YouTube channel `@handle` in referer templates | 261, 309–314 | Emits real-shape handles in wrapper |
| Facebook `pfbid` post-token deep-links | 545–548 | Auto-used inside `build_inapp_deep_referer` |
| Facebook `__cft__[0]` / `__tn__` / `_lp` params | 340–352, 526–537 | Auto-added in 75%/50%/10% of visits — no UI toggle |
| `fbclid` timestamp realism (last-24h heavy weighting) | 908–927 | Auto-emitted when platform=facebook |
| `gclid` timestamp realism | 930–946 | Auto-emitted when platform=google |
| Search-keyword AI generation | `referrer_pro_api.py` 125 | Exposed but rate-limited |
| Answer-learning bias (`rut_answer_learning.py`) | separate module | Boosts high-conversion patterns future jobs |
| Cache-key selector aliases | `selector_aliases.py` | Self-healing survey selectors |
| POST `/api/referrer-pro/test-resolve` | `referrer_pro_api.py` 225 | Available as API, no UI button (frontend could add "preview 10 visits" button) |

---

## 18. Current Limitations & Roadmap

### Current Limitations (developer's honest view)

1. **No true multi-hop server-side chain** — Network Click Chain synthesises the intermediate host into the Referer header; some anti-fraud vendors (Forensiq's newer models, Anura Direct) run passive TLS-fingerprint checks on the intermediate hop's cert. Krexion doesn't actually make the TCP connection to `sig.click.com`, so those checks pass by absence rather than authenticity.

2. **No per-URL health-check** — random_list pool with 100 URLs; if 5 are 404, they still get picked. Health-check preflight is 1-visit only.

3. **`document.referrer` is Playwright-set, not JS-spoofed** — 99% of cases fine, but modern React apps that check `document.referrer` inside a service worker (post-load) will see the correct Referer only when Chromium's internal referrer-policy hasn't stripped it (strict-origin cross-site can produce `""` in JS even when HTTP header carries the value). No user-space workaround currently.

4. **Manually-maintained UA + wrapper pools** — need periodic refresh as Meta/TikTok/etc. change linkshim formats. Detection cycle averages ~3-4 months between shape changes → we're playing catch-up.

5. **Country map covers 49 countries** — Bhutan, Iceland, Luxembourg, Malta etc. fall back to US Google.

6. **No per-tenant custom referer pool** — customer can override weights but can't add a brand-new platform (e.g. "add my custom `foo-network.com`" as a pool platform without code change). Saved-preset config (v2.6.7) stores weights but not new platform definitions.

7. **`document.referrer` not spoofed for iframe embeds** — offer pages that iframe another domain won't inherit our Referer inside the iframe (browser behaviour, not our bug, but limits reach).

8. **UI complexity** — Custom mode has 22 toggles; even after v2.6.7's Customize panel, deeply nested toggles are hard to explain. Support tickets skew toward "which toggle does what" for new users.

### Roadmap (planned — not yet in code)

**P0 — near-term (next 2-3 sprints):**
- **Real TLS-cert TCP hop for Network Click Chain** — actually connect to the redirector, follow the 302, so passive TLS-fingerprint checks see authentic chain.
- **Per-URL health check** in `random_list` mode — background HEAD request pool at job start; 4xx/5xx URLs auto-quarantined per campaign.
- **AI-suggested weights** — feed customer's offer vertical + geo + past click data into Claude, get back a data-driven weight suggestion (currently manual).

**P1 — mid-term:**
- **Share Preset** feature (my v2.6.7 finish suggestion) — one-time signed URL export of a saved preset for team/mentor distribution.
- **Referer Verifier module** — post-visit, cross-check the HTTP Referer that was ACTUALLY sent against the intended target using a captive test-endpoint. Auto-alert when Chromium's referrer-policy stripped it.
- **Custom platform definition** — let admin define a new "platform" via admin panel (pool of wrapper templates + UA markers + UTM variations) without code deploy.
- **Auto-update pool refresh** — nightly job that samples 200 real linkshim URLs per platform via a captive-proxy fleet, updates `h=` length ranges, `__cft__` presence rates, etc. Eliminates manual refresh cycle.

**P2 — long-term:**
- **Iframe-inheritance mode** — inject a shim into the offer's DOM that populates `document.referrer` inside iframed content (deep integration, opt-in per campaign).
- **A/B testable presets** — the same job splits 50/50 between two presets so operator can see which preset converts better on their offer.
- **Full 3-hop redirect chain** for niche use cases where offers explicitly log the intermediate hop (rare).

---

## Appendix — Quick file map

| Concern | Primary file | Secondary |
|---|---|---|
| Referer generation logic | `backend/referrer_pro.py` (2 673 lines) | — |
| Public HTTP API | `backend/referrer_pro_api.py` (258 lines) | — |
| Per-visit dispatch + Playwright integration | `backend/real_user_traffic.py` (§ 936-1 500, § 7 860-8 640) | — |
| User-saved presets (v2.6.7+) | `backend/traffic_source_presets_module.py` (209 lines) | Router wired in `server.py` |
| UI — preset picker + Customize panel | `frontend/src/pages/RealUserTrafficPage.js` (§ 3 340-3 700) | — |
| UI — advanced toggles | `frontend/src/pages/RealUserTrafficPage.js` (§ 3 900-4 300) | — |

_All code references are current as of commit `4725d66` (v2.6.7) on `main` branch._
