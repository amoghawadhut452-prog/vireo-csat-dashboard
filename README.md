# Vireo Audio - Agent CSAT & Handle Time Dashboard

## One-line answer
The CSAT slide is driven by the Pulse 2 (VA-EB-PL2) "left bud not charging" defect
wave, not by agent skill. Retraining the raw bottom ten would spend Priya's Rs 4 lakh on the
warranty desk, whose low CSAT is the escalation queue, not incompetence.

## Install & run (zero dollars, zero API keys)
```
pip install -r requirements.txt
streamlit run app.py
```
Tests: `python -m pytest tests/ -v`
Run cost: Rs 0 per run (no per-ticket model calls; Arjun's rejected benchmark was Rs 5 x 11,750 = ~Rs 59k).

## Files
- data_clean.py — cleaning (timezone fix, dedupe, money check, roster as-of join, SLA breach, repeat contacts)
- analysis.py — shrinkage ranking, case-mix OLS adjustment, bootstrap, hardware-rota detection, keyword classifier
- app.py — Streamlit dashboard (Tier 1 vs Tier 2 separated, CIs, bottom-ten/top-five flags, trends, hypotheses, handle time, data quality)
- hyp_test.py — H1-H6 evidence; goal_number.py — single Rs goal number; bootstrap_stability.py — rank stability
- notes/ — email_context.md, decisions.md, plan.md, versions.md, ai_usage.md, recording_outline.md, not_done.md

## Validation (measured, not claimed)
- Unit tests: 6 passed (timezone, dedupe, money numeric, roster row preservation, duplicate-name guard, blank CSAT).
- Timezone: 2,309 legacy rows had negative handle times; a +5:30 shift on legacy `resolved_at` fixes 100% (mean handle 17.1h -> 22.6h; current helpdesk median 0.50h vs fixed legacy 0.43h — same distribution). 0 negative after fix.
- Dedupe: legacy/helpdesk ticket_id overlap 0; content-key duplicates 0 — the policy's "re-imported subset" did NOT materialise; order_id overlap (160 ids) is repeat contacts months apart, not duplicates.
- Money: legacy refund/order-value ratio distribution (p10 0.15, median 1.0) matches helpdesk — no unit rescaling needed, tested not assumed.
- Roster: 44/44 agents matched, 1 row/agent (as-of join tested on 'Kavya Pandey' A3006 vs A3029; no merge).
- Blank CSAT: 55.8% blank -> excluded from means (response rate 44.2%, ~policy's ~45%).
- Auto-closed CSAT tracked separately: 3.58 pre-festive -> 3.10 festive-onward.
- Keyword root-cause classifier accuracy: 24% on a 100-ticket hand-label sample (see notes + code) -> treated as EDA only, not for headlines.

## Goal number (arithmetic shown)
Replacement rate per 1,000 tickets: ~97 (Jan-Sep 2025 baseline) -> ~175 (Apr-Jun 2026).
Defected lots/PL2: 83% of Dec-25-Mar-26 replacements are VA-EB-PL2; Pulse 2 has 1,166 of 1,896 replacements.
GOAL: **cut the replacement rate from ~17.5% back to ~9.7% — about 160 fewer replacements a quarter, worth about Rs 2.9 lakh a quarter** (160 x Rs 1,802 policy unit cost + Rs 340 mean cost weighted by actual mix). Arjun's Rs 2,500/replacement overstates the policy cost by Rs 698 (39%).
