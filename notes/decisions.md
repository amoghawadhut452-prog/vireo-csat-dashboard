# decisions.md (updated)

## Always decisions
- Trusted the size of the raw effect and the *policy formula* for replacement cost (Arjun's Rs 2,500 overstates the Rs 1,802 policy-weighted mean by Rs 698).
- Handled the README-vs-data timezone conflict by a direct test: all 2,309 negative handle times on legacy rows were fixed by +5:30h on legacy `resolved_at` only (now 0 negative). So we corrected `resolved_at` (UTC→IST) but left `created_at`/`first_response_at` as exported IST.
- Treated duplicate-name-merge risk as a test, not a worry: A3006 and A3029 stay separate, teams verified, row count preserved through merges (assert in tests).
- Duplicates across source systems: 0 on ticket_id, 0 on content key, 0 within 7-day cross-window — conclusion: the "re-imported subset" wasn't present; 160 rows sharing order_id are legitimate repeat contacts, counted under H5 (347 tickets flagged `is_repeat`).
- Money native-unit test: legacy and helpdesk refund/order-value ratio distributions are statistically identical (median ratio 1.0, p10 ~0.15), so NO rescaling was applied. Documented rather than assumed either way.
- Blank CSAT (55.8%) excluded from all averages; response counts reported per agent. Minimum n = 15 for ranking flags, plus empirical-Bayes shrinkage, plus 500-sample bootstrap stability reporting.
- Breach attribution: breach rate by team (Email 12.2% vs Voice 4.5%) and hour (mild night-hour bump); treated as a queue/shift finding, not a resolving-agent fault.
- Hardware rota identified by top-4 hardware-category fraction among Chat/Voice frontline agents: A3006 (Kavya), A3004, A3005, A3007. Warranty team = A3039-A3044. Documented in identify_hardware_rota().
- Tier 2 never compared with Tier 1 on volume or speed; dashboard separates them. Auto-closed tickets reported separately.
- Refund + replacement both-for-same-order violations: 6 tickets, refunds Rs 13,797, leak ~Rs 25,577 — small; tracked but not the headline.
- IVR junk: 26 tickets with [inaudible]/[crosstalk]/[line dropped] markers + 12 rows of 1-3-char junk = 38 ≈ "about 40" confirmed, excluded from any text labeling, never attributed to agents.
- LLM: zero paid calls. A local keyword classifier on 11,750 tickets hit 24% accuracy on a 100-ticket hand-label — disclosed in README/memo, not used for any headline.
- Festive-volume hypothesis vs defect hypothesis: replacements/1,000 tickets rose 97 → 175 in the last quarter (rate, not volume); PL2 is 83% of Dec-Mar replacements, top-5 lots 42%. Conclusion: defect wave, not festival volume.
