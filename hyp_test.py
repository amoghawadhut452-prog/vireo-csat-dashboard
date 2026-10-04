"""
Vireo Audio - structured hypothesis testing + goal number.
Prints evidence table; numbers here feed the memo (every figure traceable).
"""
import pandas as pd
import numpy as np
from data_clean import load_clean_data, POLICY_COSTS

data = load_clean_data()
t = data['tickets']
products = data['products']
orders = data['orders']

print('=' * 70)
print('HYPOTHESIS TESTING: why did CSAT slide from Oct-2025 onward?')
print('=' * 70)

CUTOFF = pd.Timestamp('2025-10-01')
t['period'] = np.where(t['created_dt'] < CUTOFF, 'pre_festive', 'festive_onward')

for period, sub in t.groupby('period'):
    print(f"\n{period}: n_tickets={len(sub)}, CSAT mean={sub['csat_score'].mean():.3f}, "
          f"mix delta: Charging share={np.mean(sub['category']=='Charging & Battery'):.3f}")

# H1 agent skill: did the SAME agents' CSAT drop, or mix changed?
agent_csat = t.groupby(['agent_id', 'period'])['csat_score'].agg(['mean', 'count'])
pre = agent_csat.xs('pre_festive', level='period')
post = agent_csat.xs('festive_onward', level='period')
both = pre.join(post, lsuffix='_pre', rsuffix='_post')
print(f"\nH1 agent skill: agents serving both periods = {len(both)}")
print(f"   mean agent-level CSAT change: {(both['mean_post']-both['mean_pre']).mean():.3f}")

# H2 transfers
for period, sub in t.groupby('period'):
    print(f"H2 transfers {period}: {(sub['transfers']>0).mean():.3f}, mean transfers/ticket={sub['transfers'].mean():.3f}")

# H3 first-response breaches by shift/hour vs agent
t['hour'] = t['created_dt'].dt.hour
t['sla_f'] = t['sla_breach'].astype(float)
for period, sub in t.groupby('period'):
    print(f"H3 breach rate {period}: {sub['sla_f'].mean():.4f}")
# breach track: hour or agent?
br = t.dropna(subset=['sla_breach'])
print('   breach rate by created hour:', br.groupby('hour')['sla_f'].mean().round(3).to_dict())
print('   breach rate by team:', br.groupby('assigned_team')['sla_f'].mean().round(3).to_dict())

# H4 product / SKU / lot
rl = t[t['replacement_issued'] == 'Y']
print(f"\nH4: replacements total={len(rl)}")
print(rl['product_sku'].value_counts().head(5))
# replacement rate per 1000 tickets by month
for m, g in t.groupby(t['created_dt'].dt.to_period('M')):
    repl = (g['replacement_issued'] == 'Y').sum()
    if m >= pd.Period('2025-11') and m <= pd.Period('2026-03'):
        print(f"   {m}: tickets={len(g)}, replacements={repl}, rate={repl/len(g)*1000:.0f}/1000")
# lot codes on replacements via order_id
repl_with_order = rl[rl['order_id'].notna()].merge(orders[['order_id', 'lot_code']], on='order_id', how='left')
print('   top replacement lots (Dec25-Mar26):')
win = repl_with_order[(repl_with_order['created_dt'] >= '2025-12-01') & (repl_with_order['created_dt'] < '2026-04-01')]
print(win['lot_code'].value_counts().head(5))

# H5 repeat contacts
for period, sub in t.groupby('period'):
    print(f"H5 repeat rate {period}: {sub['is_repeat'].mean():.4f}, cost/contact blended Rs {POLICY_COSTS['blended_contact_cost']}")

# H6 artefacts: CSAT by source system pre/post
for ss, sub in t.groupby('source_system'):
    print(f"H6 {ss}: CSAT {sub['csat_score'].mean():.3f}")

# Auto-closed CSAT
for period, sub in t.groupby('period'):
    ac = sub[sub['status'] == 'closed']['csat_score']
    print(f"Auto-closed CSAT {period}: {ac.mean():.3f} (n={ac.notna().sum()})")
