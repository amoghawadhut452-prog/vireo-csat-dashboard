# versions.md
- 10/04 2:16pm — previous pass copied email context, decisions skeleton.
- 10/04 3:00pm — Stage 0 plan in notes/plan.md; confirmed 6-hypothesis task decomposition.
- 10/04 3:25pm — Stage 1: created data_clean.py with TZ fix, dedupe test (0 dup), money check (no rescale), roster join, SLA breach, repeat-contact flag (347), tier/handle-time columns; 6 passing pytest cases.
- 10/04 3:40pm — app.py + analysis.py: fixed case-mix OLS bug (bool dummies → float; except branch set predicted), verified 6 functions via smoke test.
- 10/04 3:55pm — Stage 2: wrote hyp_test.py, goal_number.py; established PL2-dominated replacement wave (83%, rate 97→175/1000).
- 10/04 4:05pm — apptest run: dashboard boots, 0 exceptions; all five views render.
- 10/04 4:20pm — Stage 4 validation: bootstrap_stability.py (bottom-10 warranty-team dominance; top-5 max 78%), 100-ticket hand-label (keyword classifier 24% accuracy — disclosed), overlap tables.
- 10/04 4:35pm — Stage 5: README, MEMO, all notes files filled in, requirements.txt pinned.

- 10/04 5:00pm - Cleanup pass: deleted patch_app.py, re-ran bootstrap_stability.py at N_BOOT=500 (top-5 max now A3018 at 72%), removed scikit-learn from requirements.txt; README verified clean of replacement characters.
