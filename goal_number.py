"""Build the single business-goal number + headline stats with arithmetic shown."""
import pandas as pd, numpy as np
from data_clean import load_clean_data, POLICY_COSTS

data = load_clean_data()
t = data['tickets']; products = data['products']; orders = data['orders']

rl = t[t['replacement_issued'] == 'Y']
repl = rl.copy()  # tickets already carry unit_cost_inr via data_clean merge
repl['repl_cost'] = repl['unit_cost_inr'] + POLICY_COSTS['replacement_logistics']

# weighted mean policy cost per replacement (weighted by products actually replaced)
wmean = (repl['repl_cost']).mean()
print(f"Mean policy-based cost per replacement (weighted by actual mix): Rs {wmean:,.0f}")
print(f"Arjun's guesstimate: Rs 2,500  -> overstates by Rs {2500 - wmean:,.0f} ({(2500 - wmean)/wmean*100:.0f}%)")

# excess replacement rate vs pre-festive baseline
for m, g in t.groupby(t['created_dt'].dt.to_period('M')):
    pass
base = t[t['created_dt'] < pd.Timestamp('2025-10-01')]
base_rate = (base['replacement_issued'] == 'Y').mean()
late = t[(t['created_dt'] >= '2026-04-01') & (t['created_dt'] < '2026-07-01')]
late_rate = (late['replacement_issued'] == 'Y').mean()
late_n = len(late)
excess_rate = max(late_rate - base_rate, 0)
excess_repl_q = excess_rate * late_n
value = excess_repl_q * wmean
print(f"\nBaseline replacement rate (Jan-Sep25): {base_rate*1000:.0f} per 1000 tickets")
print(f"Q2-26 rate (Apr-Jun26): {late_rate*1000:.0f} per 1000 tickets")
print(f"Excess replacements/quarter at current rate: {excess_rate*1000*late_n/1000:.0f}")
print(f"GOAL: Cut replacement rate from {late_rate*100:.0f}% to {base_rate*100:.0f}% -> {excess_repl_q:.0f} fewer replacements/quarter")
print(f"     worth about Rs {value/100000:.1f} lakh/quarter ({excess_repl_q:.0f} x Rs {wmean:,.0f})")

# defects: PL2 share and lot concentration
win = repl[(repl['created_dt'] >= '2025-12-01') & (repl['created_dt'] < '2026-04-01')]
win_o = win.merge(orders[['order_id', 'lot_code']], on='order_id', how='left')
print(f"\nPL2 share of Dec25-Mar26 replacements: {(win['product_sku']=='VA-EB-PL2').mean():.2f}")
lots = win_o['lot_code'].value_counts(normalize=True).head(5)
print('top 5 lots share:', f"{lots.sum():.2f}")

# refund+replacement violations
both = t[(t['replacement_issued'] == 'Y') & t['refund_amount_inr'].notna() & (t['refund_amount_inr'] > 0)]
leak = both['refund_amount_inr'].sum() + both['unit_cost_inr'].fillna(0).sum() + POLICY_COSTS['replacement_logistics'] * len(both)
print(f"\nRefund+replacement (policy violation): {len(both)} tickets, refunds Rs {both['refund_amount_inr'].sum():,.0f}, leak ~Rs {leak:,.0f} over full period")

# replacement spend = unit cost + Rs 340, weighted
print(f"\nTotal replacement spend FY-to-date: Rs {repl['repl_cost'].sum():,.0f}")
print(f"Total refunds: Rs {t['refund_amount_inr'].sum():,.0f}")
