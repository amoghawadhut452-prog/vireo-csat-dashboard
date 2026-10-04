"""Unit tests for cleaning logic: timezone, dedupe, money, roster as-of join,
blank-CSAT handling. Run: python -m pytest tests/ -v"""
import os
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_clean import fix_timezones, dedupe_tickets, load_clean_data, LEGACY_TZ_OFFSET


def _base_rows():
    return pd.DataFrame([
        {'ticket_id': 'T1', 'source_system': 'legacy_fd',
         'created_at': '2025-03-01 12:00', 'first_response_at': '2025-03-01 12:30',
         'resolved_at': '2025-03-01 07:00', 'status': 'resolved',
         'customer_id': 'C1', 'product_sku': 'VA-EB-PL2', 'category': 'Other',
         'channel': 'chat', 'customer_message': 'm1'},
        {'ticket_id': 'T2', 'source_system': 'helpdesk',
         'created_at': '2026-01-01 10:00', 'first_response_at': '2026-01-01 10:20',
         'resolved_at': '2026-01-01 11:00', 'status': 'resolved',
         'customer_id': 'C2', 'product_sku': 'VA-EB-PL1', 'category': 'Other',
         'channel': 'chat', 'customer_message': 'm2'},
    ])


def test_legacy_timezone_fix_resolves_negative_handle():
    t = fix_timezones(_base_rows())
    h = (t['resolved_dt'] - t['first_response_dt']).dt.total_seconds() / 3600
    assert (h >= 0).all(), 'all handle times must be non-negative after +5.5h fix'
    # row 2 (helpdesk) must be untouched
    row2 = t[t['ticket_id'] == 'T2'].iloc[0]
    assert row2['resolved_dt'] == row2['resolved_raw_dt']


def test_dedupe_counts_duplicates():
    rows = pd.concat([_base_rows(), _base_rows().iloc[[0]]], ignore_index=True)
    out, counts = dedupe_tickets(rows)
    assert counts['dup_ticket_id'] == 1


def test_blank_csat_is_not_zero():
    data = load_clean_data()
    t = data['tickets']
    with_csat = t['csat_score'].notna()
    assert with_csat.sum() > 0
    # blank stays NaN, mean excludes them (vs treating as 0)
    naive_zero = t['csat_score'].fillna(0).mean()
    assert t['csat_score'].mean() != naive_zero


def test_roster_join_preserves_row_count():
    data = load_clean_data()
    t = data['tickets']
    # one row per ticket guaranteed after merges
    assert len(t) == data['dedup_counts']['rows_in']
    # every agent matched
    assert t['tier'].notna().all()


def test_no_rows_merged_across_identical_names():
    data = load_clean_data()
    agents = data['agents']
    kavya = agents[agents['name'] == 'Kavya Pandey']
    assert kavya['agent_id'].nunique() == 2, 'two distinct Kavya Pandey rows expected'
    t = data['tickets']
    assert t.loc[t['agent_id'] == 'A3006', 'team_roster'].iloc[0] == 'Chat Frontline'
    assert t.loc[t['agent_id'] == 'A3029', 'team_roster'].iloc[0] == 'Logistics'


def test_handle_time_non_negative_and_money_numeric():
    data = load_clean_data()
    t = data['tickets']
    assert (t['handle_time_hrs'].dropna() >= 0).all()
    assert pd.api.types.is_numeric_dtype(t['refund_amount_inr'])
