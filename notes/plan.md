# Plan (T0 = 2026-10-04) — 5h human budget

| Stage | Task | Est |
|---|---|---|
| 0 | Read README/email/policy, notes/email_context.md + decisions.md | 15m (done) |
| 1 | data_clean.py (timezone fix, dedupe test, money test, roster as-of join, blank CSAT, SLA breach, repeat contacts, handle time) + pytest | 60m |
| 2 | Hypothesis testing (H1–H6), replacement-doubling test, replacement-cost Arjun vs policy, goal number | 60m |
| 3 | Dashboard (Streamlit, working) | 45m |
| 4 | Validation: pytest run, hand-label ~100, confusion matrix, bootstrap stability, raw vs adjusted bottom-ten overlap | 45m |
| 5 | README, memo, notes (ai_usage, recording_outline, not_done, versions) | 45m |
| Buffer | — | 30m |

# Stage summaries

## Stage 0
- Email/policy context captured in notes/email_context.md and notes/decisions.md (prior pass).
- Key conflicts logged: legacy resolved_at UTC vs IST display; Arjun Rs 2500 vs policy unit_cost+340; replacements doubling — festive vs defect (VA-EB-PL2 pulse 2 replacements dominate; Pulse 2 launched 2025-07-15, rate spiked Dec25–Mar26).
- Data profiling: 11750 tickets, 44 agents, CSAT blank 55.8%, legacy resolved_at needs +5.5h shift (all 2309 negative handle times fixed), replacement rate ~100/1000 Jan–Nov25 → ~250/1000 Dec25–Mar26.
