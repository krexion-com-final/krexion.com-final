# Krexion — PRD (Product Requirements Document)
_Last updated: 2026-02-20 · Session v2.6.15_

## Original Problem Statement
Customer runs a self-hosted RUT (Real-User-Traffic) SaaS. Repo:
krexion-com-final/krexion.com-final. Auto-deploys via GitHub Actions
to VPS + Electron + Native Windows builds on every push to main.
Customer wants zero-conflict, everything-perfect changes with
save-to-github done via Emergent's platform button.

## Session Timeline (my contribution)
- **v2.6.3** (initial): DataImpulse targeting engine — Country/State/City/ZIP/ISP auto-detect for 8 providers; dual-mode SearchableCombo UI; universal geo-targeting on Proxies page.
- **v2.6.4** (unpushed staging): ERR_ABORTED false-failure guard + desktop-UA-to-mobile swap for in-app platforms + blank-referer safety net.
- **v2.6.5**: In-App Browser Preset now preserves operator's Custom Referrer URL — TikTok/FB/IG etc. preset only overrides referer when operator hasn't picked one. Fixes real ad-flow simulation.
- **v2.6.15** (current): Duplicate-IP false-positive fix — pre-browser dup probe (`_probe_offer_duplicate_via_proxy`) was hitting offer domain root a SECOND time via httpx from the same exit IP after the reachability probe. Strict trackers (Traxun, Voluum, RedTrack, Binom) counted consecutive same-IP hits as duplicate sessions → 403 on browser goto. Fix: disabled the redundant pre-browser dup probe; post-load block detector (uses browser's own response body — no extra HTTP hit) unchanged. Browser goto is now the SOLE tracker-touching hit per visit.

## Post-v2.6.5 Collaborator Releases (I've read these)
- v2.6.7: Baseline referrer system doc (`memory/REFERRER_SYSTEM_DOCUMENTATION.md`)
- v2.6.8-9: RUT Customize Preset + Saved Presets (`backend/traffic_source_presets_module.py`)
- v2.6.10: Provider IP Quality Layer + initial custom-referrer guarantee
- v2.6.11: Duplicate-IP click leak fix (probe → domain root only) + Feb-2026 UA refresh
- v2.6.12: Parallel concurrency + TikTok preset safety net + Caddy self-heal workflows
- v2.6.13: Referer force-injection via `context.route` (100% referer guarantee on cross-origin nav) + F821 fixes
- v2.6.14: Rotating-gateway proxy exhaustion fix (50+ providers auto-detected) + offer-block auto-retry combined flag

## Architecture Notes (do NOT re-invent)
- Referer force-injection: `_make_macro_guard` in `real_user_traffic.py` accepts `force_referer` and injects via `context.route` per-document nav. This is the current mechanism.
- Rotating gateway detection: `_detect_rotating_gateway()` in `proxy_provider_module.py` — recognizes 50+ providers by hostname suffix/prefix + session marker in username.
- Concurrency: batch staggering `_target_offset = (i // conc) * delay_between` — real parallelism, first `conc` workers fire at t=0.
- Caddyfile is git-tracked (must survive `rsync --delete` on VPS deploy).
- Bare `except:` blocks silently swallowed NameError historically. All added exception handlers must specify class and log.
- `.emergent/` platform files are in `.git/info/exclude` (local-only) — never pushed to main.

## Hidden Features (backend exists, no UI yet — potential quick wins)
- `campaign_type` (prospecting/remarketing/lookalike/...)
- `quality_tier` (basic/standard/premium/enterprise)
- `tod_enabled` (time-of-day weighting)
- `device_mode` (mobile_only/desktop_only/match_platform)
- `lang_match` (auto Accept-Language from country)
- `POST /api/referrer-pro/test-resolve` (preview N referers before running job)

## Deferred / Next Session (per user's explicit request)
### Task 1 — AI Auto-Recorder (Visual Recorder module)
Hybrid multi-provider approach:
- Default: Gemini 3 Flash (~$0.01/recording)
- Premium: Claude Sonnet 4.5 (~$0.15/recording)
- Balanced: GPT-5.2 (~$0.10/recording)
- Trial fallback: Emergent LLM key (customer needs no key of their own)

Customer describes conversion flow in plain English → AI opens offer via Krexion browser+proxy → 4-5 iterations of (screenshot + DOM snapshot + AI decides next action + Krexion executes) → on success, AI emits JSON script for Visual Recorder editor.

MVP scope (~1 week):
1. Backend: new endpoint POST /api/visual-recorder/ai-record (streams progress)
2. Backend: AI orchestrator + provider adapters (Gemini/Claude/OpenAI/Emergent)
3. Backend: selector verifier layer (prevent AI-hallucinated selectors)
4. Frontend: Visual Recorder modal + real-time progress UI + JSON preview
5. Settings page: AI provider dropdown + BYOK API key + Emergent LLM key toggle

## Backlog (from REFERRER_SYSTEM_DOCUMENTATION.md § 18)
- P0: Real TLS-cert TCP hop for Network Click Chain; per-URL health check in random_list; AI-suggested weights per offer vertical+geo
- P1: Share Preset feature; Referer Verifier module; Custom platform definition; Auto-update pool refresh
- P2: Iframe-inheritance mode; A/B testable presets; Full 3-hop redirect chain

## Deployment Status (v2.6.15 — this session)
- Pushed to origin/main: commit a8c2324
- Workflows triggered (all 3): Deploy VPS + Electron desktop + Native Windows
- Expected completion: 25-40 min from push
- Customer will verify by rerunning samsclub01 campaign — visits should land HTTP 200/302 with no burnt IPs
