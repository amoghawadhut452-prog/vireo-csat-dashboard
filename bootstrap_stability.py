"""Bootstrap stability of bottom-ten / top-five flags; raw vs adjusted overlap."""
import pandas as pd, numpy as np
from collections import defaultdict
import data_clean, analysis

d = data_clean.load_clean_data()
t = d['tickets']
N_BOOT = 500  # matched to app.py bootstrap count

# raw vs adjusted bottom-ten overlap
raw = analysis.compute_agent_csat_with_shrinkage(t)
adj, r2, at = analysis.case_mix_adjustment(t)
raw_b10 = set(raw.sort_values('shrunk_mean').head(10)['agent_id'])
adj_b10 = set(adj.sort_values('shrunk_adjusted').head(10)['agent_id'])
print(f"raw vs adjusted bottom-10 overlap: {len(raw_b10 & adj_b10)}/10")
raw_t5 = set(raw.sort_values('shrunk_mean').tail(5)['agent_id'])
adj_t5 = set(adj.sort_values('shrunk_adjusted').tail(5)['agent_id'])
print(f"raw vs adjusted top-5 overlap: {len(raw_t5 & adj_t5)}/5")

# bootstrap
has = t[t['csat_score'].notna()]
bottom_ctr = defaultdict(int); top_ctr = defaultdict(int)
for i in range(N_BOOT):
    idx = has.groupby('agent_id', group_keys=False).apply(lambda x: x.sample(len(x), replace=True), include_groups=False).index
    bs = has.loc[idx]
    rs = analysis.compute_agent_csat_with_shrinkage(bs, min_n=15)
    rs = rs[rs['sufficient_n']]
    for a in rs.nsmallest(10, 'shrunk_mean')['agent_id']:
        bottom_ctr[a] += 1
    for a in rs.nlargest(5, 'shrunk_mean')['agent_id']:
        top_ctr[a] += 1
print('\nBottom-10 stability (P of appearing):')
for a, c in sorted(bottom_ctr.items(), key=lambda x: -x[1]):
    print(f"  {a}: {c/N_BOOT:.0%}")
print('\nTop-5 stability:')
for a, c in sorted(top_ctr.items(), key=lambda x: -x[1]):
    print(f"  {a}: {c/N_BOOT:.0%}")
