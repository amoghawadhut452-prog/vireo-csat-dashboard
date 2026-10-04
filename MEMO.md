# MEMO — Draft for Priya Raman, Head of CX (Vireo Audio)
Non-technical, ~6 min read. Every figure traces to a script in this repo.

## The answer first
Do **not** retrain the raw bottom ten. The CSAT slide is mostly a Pulse 2 defect wave, not a people problem:
- CSAT fell 3.49 (Jan-Sep 2025) to 3.25 (Dec 2025 onward), bottoming at 2.95 in Feb 2026.
- Case-mix only explains ~19% of CSAT variance, but nearly all of *where* CSAT is low is explained by which queue you are in:
  - Charging & Battery tickets rate 2.73 vs 3.8+ for Account & Login and Product Enquiry.
  - Replacements ran ~97 per 1,000 tickets in 2025, peaked at ~255 in Jan-Mar 2026. 83% of those were the same SKU: VA-EB-PL2 ("left bud won't charge"). Top five manufacturing lots account for 42% of Dec-Mar replacements.
- The raw bottom-five quartile is the entire warranty team (A3039-A3044, all >99% likely to appear in the bottom ten) plus four chat agents who we identify as the hardware-triage rota. Their low scores are the queue, not the person. Neha's warning in the email thread is borne out.

## The one money number (goal)
**Cut the replacement rate from ~17.5% (now) back to ~9.7% (2025 baseline) — about 160 fewer replacements per quarter, worth about Rs 2.9 lakh a quarter.**
Replacement cost per unit = product unit cost + Rs 340 logistics = Rs 1,802 on average across the mix actually replaced. That Rs 2.9 lakh/quarter dwarfs the refund/replacement policy breaches we found (~Rs 25k total across all of FY) and the repeat-contact waste. Spend the triage effort on the PL2 manufacturing/inspection fault, not on frontline agents.
(goal_number.py shows the arithmetic; scripts/hyp_test.py shows the tests.)

## What to do with the Rs 4 lakh (split)
- **Rs 2.4 lakh (~60%) → field quality, not people:** root-cause the PL2 charging defect with the vendor, push a warranty/RMA comms tweak, publish a customer advisory on the fix firmware. Saves the 160 replacements/quarter and will move CSAT more than any training.
- **Rs 1.0 lakh (~25%) → genuine training, but targeted:** the two signal we kept: (a) Email Frontline's first-response breach rate is 12% vs 4.5% for Voice and ~8% overall — that's a queue/shift coverage fix, rides on shifts, not scolding; (b) the auto-closed cohort's CSAT dropped from 3.58 (2025) to 3.10 — a quality-check step on auto-closed closures (~Rs 60k) is cheap insurance.
- **Rs 0.6 lakh (~15%) → confidence engineering on the data:** the dashboard needs three sprints' more repeats before anyone's name sits on a Diwali list. Budget for hand-labels of a 100-ticket root-cause sample (our keyword classifier hit only 24% accuracy — do not use it for any decision today) and one-off vendor QA before crediting a person.

## Is the Diwali top five safe to award?
**No, not with the confidence a cash bonus deserves.** The top-five membership is unstable:
- Raw vs case-mix adjusted top-five overlap: 3 of 5 agents.
- Bootstrap (500 resamples): the most stable top-five agent appears 72% of the time; most agents sit at 20-50%. P(top-5) is not a ranking we can pay a Diwali bonus on.
Recommendation: award the bonus only to agents that appear in the top five across raw, adjusted, and bootstrap-stable (>70%) lenses. Agent A3018 (72%) is the only one that clears a 70% bar today.

## Replacement-cost arithmetic (Arjun vs policy)
- Arjun: ~Rs 2,500/replacement.
- Policy: unit cost + Rs 340.
- Policy-weighted mean across the products actually replaced: **Rs 1,802**. Arjun overstates by Rs 698 (~39%). Both agree on the disturbing part: replacement volume is the real problem, and it's rising.

## What the dashboard already answers (Priya's ask, delivered)
Per-agent CSAT and handle time, Tier-2 separated, tier-1 only flagged, confidence intervals, sample sizes, case-mix adjustment, hardware-rota flag, bootstrap rank stability, raw-vs-adjusted bottom-ten overlap (only 5 of 10 overlap → instinct vs shipment must differ), trends by month/channel/SKU/lot, breach-by-hour-by-shift.

## Risks we are calling out
1. **Don't trust 24% keyword classifier output** in front of a customer. Structured outcomes are our evidence.
2. Legacy timestamps were reconstructed from a UTC log — we repaired 2,309 of them (+5:30) but legacy handle times carry ±hour uncertainty.
3. No true duplicates found, but the policy said some were re-imported — if anyone has the Freshdesk extract, rerun the join key.
4. VPN of certainty: two agents share "Kavya Pandey" — the rota identified (A3006, A3004, A3005, A3007) is by hardware-category share, verified by A3006 vs A3029.

## What we did NOT do, and why
- Per-ticket LLM labelling (Arjun's Rs 5 x ~12k = ~Rs 60k ruled out; local rules + hand-labels instead, cached).
- Forecasting FY27 volume or per-customer views (gold-plating for a 5-hour brief).
- Rank agents on raw means (rejected: 55.8% blank CSAT, n=100 vs 500 per agent).

Run cost: Rs 0 (script + Streamlit, no external calls). New runs are free; only the hand-labels used hours.
