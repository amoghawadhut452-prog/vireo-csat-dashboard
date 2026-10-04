"""
Vireo Audio - Comprehensive Data Audit
Checks every data trap from the requirements.
"""
import pandas as pd
import numpy as np
from datetime import timedelta

# ── Load data ──
tickets = pd.read_csv('tickets.csv')
agents  = pd.read_csv('agents.csv')
orders  = pd.read_csv('orders.csv')
customers = pd.read_csv('customers.csv')
products = pd.read_csv('products.csv')

print("="*60)
print("VIREO AUDIO DATA AUDIT")
print("="*60)

# ── 1. Row counts ──
print(f"\n1. ROW COUNTS")
print(f"   tickets:   {len(tickets)}")
print(f"   agents:    {len(agents)}")
print(f"   orders:    {len(orders)}")
print(f"   customers: {len(customers)}")
print(f"   products:  {len(products)}")

# ── 2. Blank CSAT ──
blank_csat = tickets['csat_score'].isna().sum()
filled_csat = tickets['csat_score'].notna().sum()
pct_response = filled_csat / len(tickets) * 100
print(f"\n2. BLANK CSAT")
print(f"   Blank: {blank_csat} ({blank_csat/len(tickets)*100:.1f}%)")
print(f"   Filled: {filled_csat} ({pct_response:.1f}%)")
print(f"   Mean CSAT (excl blank): {tickets['csat_score'].mean():.2f}")
print(f"   CSAT distribution: {tickets['csat_score'].value_counts().sort_index().to_dict()}")

# ── 3. Duplicate display names ──
print(f"\n3. DUPLICATE DISPLAY NAMES")
name_counts = agents.groupby('name')['agent_id'].nunique()
dups = name_counts[name_counts > 1]
for name, cnt in dups.items():
    ids = agents[agents['name']==name]['agent_id'].unique()
    print(f"   '{name}' -> agent_ids: {ids} (teams: {agents[agents['name']==name]['team'].values})")

# ── 4. Source system + Legacy dedup ──
print(f"\n4. SOURCE SYSTEM")
print(f"   {tickets['source_system'].value_counts().to_dict()}")
legacy = tickets[tickets['source_system']=='legacy_fd']
current = tickets[tickets['source_system']=='helpdesk']
print(f"   Legacy tickets: {len(legacy)}")
print(f"   Current tickets: {len(current)}")

# Check for duplicate ticket_ids across both systems
both = set(legacy['ticket_id']) & set(current['ticket_id'])
print(f"   Ticket IDs appearing in BOTH systems: {len(both)}")
if len(both) > 0:
    print(f"   Sample duplicates: {list(both)[:5]}")

# Check date ranges
tickets['created_dt'] = pd.to_datetime(tickets['created_at'])
print(f"   Legacy date range: {legacy['created_at'].min()} to {legacy['created_at'].max()}")
cutover = pd.Timestamp('2025-09-14')
legacy_after_cutover = legacy[pd.to_datetime(legacy['created_at']) > cutover]
print(f"   Legacy tickets AFTER cutover (14 Sep 2025): {len(legacy_after_cutover)}")

# ── 5. Timezone / handle time check ──
print(f"\n5. TIMEZONE CHECK")
tickets['first_resp_dt'] = pd.to_datetime(tickets['first_response_at'])
tickets['resolved_dt'] = pd.to_datetime(tickets['resolved_at'])
tickets['handle_hrs'] = (tickets['resolved_dt'] - tickets['first_resp_dt']).dt.total_seconds() / 3600.0

# Check for negative handle times
neg_handle = tickets[tickets['handle_hrs'] < 0]
print(f"   Negative handle times: {len(neg_handle)}")
if len(neg_handle) > 0:
    print(f"     By source_system: {neg_handle['source_system'].value_counts().to_dict()}")
    print(f"     Sample:")
    for _, r in neg_handle.head(5).iterrows():
        print(f"       {r['ticket_id']}: first_resp={r['first_response_at']}, resolved={r['resolved_at']}, source={r['source_system']}")

# Check resolved_at < created_at (implausible)
tickets['resolve_delay_hrs'] = (tickets['resolved_dt'] - tickets['created_dt']).dt.total_seconds() / 3600.0
implausible = tickets[tickets['resolve_delay_hrs'] < 0]
print(f"   Resolved BEFORE created: {len(implausible)}")
if len(implausible) > 0:
    print(f"     By source_system: {implausible['source_system'].value_counts().to_dict()}")

# Test 5.5h offset hypothesis on legacy
legacy_neg = neg_handle[neg_handle['source_system']=='legacy_fd']
if len(legacy_neg) > 0:
    print(f"\n   Testing 5.5h offset fix on {len(legacy_neg)} legacy negative-handle tickets:")
    fixed = (tickets.loc[legacy_neg.index, 'resolved_dt'] + timedelta(hours=5.5) - tickets.loc[legacy_neg.index, 'first_resp_dt']).dt.total_seconds() / 3600.0
    still_neg = (fixed < 0).sum()
    print(f"     After +5.5h: still negative: {still_neg}, now positive: {len(legacy_neg)-still_neg}")

# Broader test: all legacy tickets
legacy_idx = tickets[tickets['source_system']=='legacy_fd'].index
legacy_handle = tickets.loc[legacy_idx, 'handle_hrs']
print(f"\n   Legacy handle time stats (raw):")
print(f"     mean={legacy_handle.mean():.2f}h, median={legacy_handle.median():.2f}h, <0: {(legacy_handle<0).sum()}")
legacy_handle_fixed = ((tickets.loc[legacy_idx, 'resolved_dt'] + timedelta(hours=5.5)) - tickets.loc[legacy_idx, 'first_resp_dt']).dt.total_seconds() / 3600.0
print(f"   Legacy handle time stats (+5.5h fix):")
print(f"     mean={legacy_handle_fixed.mean():.2f}h, median={legacy_handle_fixed.median():.2f}h, <0: {(legacy_handle_fixed<0).sum()}")

# Current helpdesk handle time for comparison
curr_idx = tickets[tickets['source_system']=='helpdesk'].index
curr_handle = tickets.loc[curr_idx, 'handle_hrs']
print(f"   Current helpdesk handle time stats:")
print(f"     mean={curr_handle.mean():.2f}h, median={curr_handle.median():.2f}h, <0: {(curr_handle<0).sum()}")

# ── 6. Money / refund magnitude check ──
print(f"\n6. MONEY CHECK")
refunds = tickets[tickets['refund_amount_inr'].notna()]
print(f"   Tickets with refunds: {len(refunds)}")
print(f"   Refund range: {refunds['refund_amount_inr'].min():.0f} to {refunds['refund_amount_inr'].max():.0f}")
print(f"   Refund mean: {refunds['refund_amount_inr'].mean():.0f}")
print(f"   By source_system:")
for ss in refunds['source_system'].unique():
    sub = refunds[refunds['source_system']==ss]['refund_amount_inr']
    print(f"     {ss}: n={len(sub)}, min={sub.min():.0f}, max={sub.max():.0f}, mean={sub.mean():.0f}, median={sub.median():.0f}")

# Detect non-rupee amounts (legacy might store in paise or different unit)
tiny_refunds = refunds[refunds['refund_amount_inr'] < 10]
print(f"   Suspiciously small refunds (<10): {len(tiny_refunds)}")
huge_refunds = refunds[refunds['refund_amount_inr'] > 20000]
print(f"   Suspiciously large refunds (>20000): {len(huge_refunds)}")

# ── 7. Refund + Replacement violations ──
print(f"\n7. REFUND + REPLACEMENT VIOLATIONS")
has_refund = tickets['refund_amount_inr'].notna() & (tickets['refund_amount_inr'] > 0)
has_repl = tickets['replacement_issued'] == 'Y'
both_mask = has_refund & has_repl
print(f"   Tickets with BOTH refund AND replacement: {both_mask.sum()}")
if both_mask.sum() > 0:
    violations = tickets[both_mask]
    # Cost the leak
    violation_orders = violations.merge(products, left_on='product_sku', right_on='sku', how='left')
    replacement_cost = violation_orders['unit_cost_inr'].fillna(0) + 340
    refund_cost = violations['refund_amount_inr'].values
    total_leak = refund_cost.sum() + replacement_cost.sum()
    print(f"   Refund total on violations: Rs {refund_cost.sum():.0f}")
    print(f"   Replacement cost on violations: Rs {replacement_cost.sum():.0f}")
    print(f"   Total leak: Rs {total_leak:.0f}")

# ── 8. Refund reason code check ──
print(f"\n8. REFUND REASON CODES")
print(f"   {tickets['refund_reason_code'].value_counts().to_dict()}")
# GW-OTHER misuse: check if it's used where a specific code applies
gw_other = tickets[tickets['refund_reason_code']=='GW-OTHER']
print(f"   GW-OTHER count: {len(gw_other)}")

# ── 9. Roster as-of join test ──
print(f"\n9. ROSTER VALIDATION")
unique_agents_tickets = tickets['agent_id'].nunique()
unique_agents_roster = agents['agent_id'].nunique()
print(f"   Unique agent_ids in tickets: {unique_agents_tickets}")
print(f"   Unique agent_ids in roster: {unique_agents_roster}")
missing = set(tickets['agent_id'].dropna()) - set(agents['agent_id'])
print(f"   Agent_ids in tickets but NOT in roster: {missing}")
# Multi-row agents
multi_row = agents.groupby('agent_id').size()
print(f"   Agents with >1 roster row: {(multi_row>1).sum()}")
if (multi_row>1).sum() > 0:
    for aid in multi_row[multi_row>1].index:
        print(f"     {aid}: {multi_row[aid]} rows")

# ── 10. IVR junk ──
print(f"\n10. IVR JUNK")
voice = tickets[tickets['channel']=='voice']
print(f"   Voice tickets: {len(voice)}")
# IVR junk: look for patterns like gibberish, very short, or known IVR artifacts
# Check customer_message for voice tickets
voice_msgs = voice['customer_message'].fillna('')
short_msgs = voice_msgs[voice_msgs.str.len() < 10]
has_ivr_pattern = voice_msgs[voice_msgs.str.contains(r'(DTMF|IVR|silence|inaudible|<noise>|\[unintelligible\]|###|beep)', case=False, na=False)]
print(f"   Voice tickets with IVR pattern in message: {len(has_ivr_pattern)}")
print(f"   Voice tickets with very short message (<10 chars): {len(short_msgs)}")
# Also check for junk in all channels
all_junk = tickets[tickets['customer_message'].fillna('').str.contains(r'(DTMF|IVR|silence|inaudible|<noise>|\[unintelligible\]|###|static|garbled)', case=False, na=False)]
print(f"   All tickets with junk IVR patterns: {len(all_junk)}")

# ── 11. Auto-closed tickets ──
print(f"\n11. AUTO-CLOSED TICKETS")
auto_closed = tickets[tickets['status']=='closed']
print(f"   Status=closed (auto-closed, no customer reply): {len(auto_closed)}")
closed_csat = auto_closed['csat_score']
print(f"   Auto-closed with CSAT: {closed_csat.notna().sum()}")
print(f"   Auto-closed mean CSAT: {closed_csat.mean():.2f}" if closed_csat.notna().sum() > 0 else "   No CSAT on auto-closed")

# ── 12. Replacement doubling ──
print(f"\n12. REPLACEMENT TREND")
repl_tickets = tickets[tickets['replacement_issued']=='Y'].copy()
repl_tickets['month'] = pd.to_datetime(repl_tickets['created_at']).dt.to_period('M')
monthly_repl = repl_tickets.groupby('month').size()
print(f"   Replacements by month:")
for m, c in monthly_repl.items():
    total_month = len(tickets[pd.to_datetime(tickets['created_at']).dt.to_period('M')==m])
    rate = c/total_month*1000
    print(f"     {m}: {c} replacements, {total_month} total tickets, rate={rate:.0f}/1000")

# ── 13. Replacement cost check (Arjun vs Policy) ──
print(f"\n13. REPLACEMENT COST: ARJUN vs POLICY")
repl_with_cost = repl_tickets.merge(products, left_on='product_sku', right_on='sku', how='left')
repl_with_cost['policy_cost'] = repl_with_cost['unit_cost_inr'] + 340
mean_policy_cost = repl_with_cost['policy_cost'].mean()
print(f"   Mean policy-based replacement cost: Rs {mean_policy_cost:.0f}")
print(f"   Arjun's estimate: ~Rs 2,500")
print(f"   Difference: Rs {mean_policy_cost - 2500:.0f} ({'Arjun over' if mean_policy_cost < 2500 else 'Arjun under'})")
print(f"   By SKU:")
for sku in repl_with_cost['product_sku'].value_counts().head(5).index:
    sub = repl_with_cost[repl_with_cost['product_sku']==sku]
    print(f"     {sku}: n={len(sub)}, policy_cost=Rs {sub['policy_cost'].iloc[0]:.0f}")

# ── 14. Order join match rate ──
print(f"\n14. ORDER JOIN")
has_order = tickets['order_id'].notna()
print(f"   Tickets with order_id: {has_order.sum()}")
print(f"   Tickets without order_id: {(~has_order).sum()}")
matched = tickets[has_order].merge(orders, on='order_id', how='inner')
print(f"   Matched to orders on order_id: {len(matched)}")
# Fallback: customer_id + product_sku
no_order = tickets[~has_order]
fallback = no_order.merge(orders, left_on=['customer_id','product_sku'], right_on=['customer_id','sku'], how='inner')
print(f"   Fallback matched (customer_id+sku): {len(fallback)}")

# ── 15. Transfers ──
print(f"\n15. TRANSFERS")
print(f"   Transfer distribution: {tickets['transfers'].value_counts().sort_index().to_dict()}")
print(f"   Mean transfers: {tickets['transfers'].mean():.2f}")

# ── 16. Category re-tagging (bot vs agent) ──
print(f"\n16. CATEGORIES")
print(f"   {tickets['category'].value_counts().to_dict()}")

# ── 17. Status distribution ──
print(f"\n17. STATUS")
print(f"   {tickets['status'].value_counts().to_dict()}")

# ── 18. Channel distribution ──
print(f"\n18. CHANNELS")
print(f"   {tickets['channel'].value_counts().to_dict()}")

# ── 19. Priority ──
print(f"\n19. PRIORITY")
print(f"   {tickets['priority'].value_counts().to_dict()}")

# ── 20. Teams ──
print(f"\n20. TEAMS")
print(f"   {tickets['assigned_team'].value_counts().to_dict()}")

print("\n" + "="*60)
print("AUDIT COMPLETE")
print("="*60)
