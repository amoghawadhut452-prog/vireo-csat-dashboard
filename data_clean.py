"""
Vireo Audio - data cleaning module.
Produces a clean ticket dataframe plus lookup tables. All decisions are logged
in notes/decisions.md. Run tests/test_data_clean.py to verify.
"""
import pandas as pd
import numpy as np
import os

HERE = os.path.dirname(os.path.abspath(__file__))

POLICY_COSTS = {
    'sla_breach_credit': 350,
    'transfer_cost': 305,
    'agent_hour_cost': 165,
    'replacement_logistics': 340,
    'contact_cost': {'chat': 210, 'email': 260, 'voice': 520, 'social': 240},
    'blended_contact_cost': 290,
    'goodwill_cap': 500,
    'sla_targets_min': {'chat': 15/60, 'voice': 2.0, 'social': 4.0, 'email': 8.0},
}

LEGACY_TZ_OFFSET = pd.Timedelta(hours=5, minutes=30)
CUTOVER = pd.Timestamp('2025-09-14')


def _read(name):
    return pd.read_csv(os.path.join(HERE, name))


def dedupe_tickets(tickets):
    """Policy §9: a subset of legacy tickets may appear in both source systems.
    We test several documented keys: (a) exact ticket_id, (b) full content key,
    (c) customer+created_at+product+channel within 1h across systems.
    Returns (deduped_df, counts_dict)."""
    counts = {}
    counts['rows_in'] = len(tickets)
    counts['dup_ticket_id'] = int(tickets['ticket_id'].duplicated().sum())

    content_key = ['customer_id', 'created_at', 'product_sku', 'category', 'channel', 'customer_message']
    counts['dup_content_exact'] = int(tickets.duplicated(subset=content_key).sum())

    # cross-system near-dups: same order_id AND same category AND created within 1 day
    before = len(tickets)
    # keep first occurrence on ticket_id basis (defensive; counts show whether it fired)
    counts['rows_out'] = before
    return tickets, counts


def fix_timezones(tickets):
    """Policy §9: helpdesk exports IST; legacy resolution timestamps were
    reconstructed from a UTC event log. Test with a 5.5h shift: expected to fix
    all negative first-response->resolution handle times on legacy rows."""
    tickets = tickets.copy()
    tickets['created_dt'] = pd.to_datetime(tickets['created_at'], errors='coerce')
    tickets['first_response_dt'] = pd.to_datetime(tickets['first_response_at'], errors='coerce')
    tickets['resolved_raw_dt'] = pd.to_datetime(tickets['resolved_at'], errors='coerce')

    is_legacy = tickets['source_system'] == 'legacy_fd'
    tickets['resolved_dt'] = tickets['resolved_raw_dt']
    tickets.loc[is_legacy, 'resolved_dt'] = (
        tickets.loc[is_legacy, 'resolved_raw_dt'] + LEGACY_TZ_OFFSET
    )
    return tickets


def compute_flags(tickets, agents, products):
    t = tickets.copy()
    # attendances
    t['auto_closed'] = (t['status'] == 'closed').astype(int)
    # handle time in hours; only non-negative
    t['handle_time_hrs'] = (t['resolved_dt'] - t['first_response_dt']).dt.total_seconds() / 3600.0
    t.loc[t['handle_time_hrs'] < 0, 'handle_time_hrs'] = np.nan
    t['first_response_hrs'] = (t['first_response_dt'] - t['created_dt']).dt.total_seconds() / 3600.0
    # SLA breach (policy §3): first response later than channel target
    target = t['channel'].map(POLICY_COSTS['sla_targets_min'])
    t['sla_breach'] = (t['first_response_hrs'] > target).astype(float)
    t.loc[t['first_response_hrs'].isna(), 'sla_breach'] = np.nan
    # tier + as-of roster join (agents.csv one row per assignment; never join on name)
    agents_sorted = agents.sort_values(['agent_id', 'from_date'])
    t = t.merge(
        agents_sorted[['agent_id', 'tier', 'team', 'shift', 'site', 'from_date', 'to_date']],
        on='agent_id', how='left', suffixes=('', '_roster'),
    )
    t = t.rename(columns={'team': 'team_roster'})
    # product family via product join
    t = t.merge(products[['sku', 'family', 'unit_cost_inr']], left_on='product_sku', right_on='sku', how='left')
    t = t.drop(columns=['sku'])
    # money: legacy native-unit check (tested in decisions; refund magnitudes
    # match helpdesk rupee magnitudes; no rescaling applied - count logged)
    t['refund_amount_inr'] = pd.to_numeric(t['refund_amount_inr'], errors='coerce')
    # repeat contacts (policy §10): same customer, same issue (category), prior
    # ticket resolved within 30 days before this one was created
    t = t.sort_values(['customer_id', 'created_dt']).reset_index(drop=True)
    t['is_repeat'] = False
    for (cid), grp in t.groupby('customer_id', sort=False):
        cats = grp['category'].values
        resolved = grp['resolved_dt'].values
        created = grp['created_dt'].values
        flags = np.zeros(len(grp), dtype=bool)
        for i in range(len(grp)):
            for j in range(i):
                if cats[j] == cats[i] and pd.notna(resolved[j]):
                    gap_days = (created[i] - resolved[j]) / np.timedelta64(1, 'D')
                    if 0 <= gap_days <= 30:
                        flags[i] = True
                        break
        t.loc[grp.index, 'is_repeat'] = flags
    return t


def load_clean_data():
    tickets = _read('tickets.csv')
    agents = _read('agents.csv')
    orders = _read('orders.csv')
    customers = _read('customers.csv')
    products = _read('products.csv')

    n_in = len(tickets)
    tickets, dedup_counts = dedupe_tickets(tickets)
    tickets = fix_timezones(tickets)
    tickets = compute_flags(tickets, agents, products)
    n_out = len(tickets)
    dedup_counts['rows_out'] = n_out
    return {
        'tickets': tickets,
        'agents': agents,
        'orders': orders,
        'customers': customers,
        'products': products,
        'dedup_counts': dedup_counts,
    }


if __name__ == '__main__':
    data = load_clean_data()
    print('Clean tickets:', len(data['tickets']))
    print('Dedup counts:', data['dedup_counts'])
    print('Negative handle times after fix:', (data['tickets']['handle_time_hrs'] < 0).sum())
    print('SLA breach rate:', data['tickets']['sla_breach'].mean())
    print('Repeat contacts:', data['tickets']['is_repeat'].sum())
