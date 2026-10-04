"""
Vireo Audio - CSAT Analysis Module
Hypothesis testing, case-mix adjustment, ranking with uncertainty.
"""
import pandas as pd
import numpy as np
from scipy import stats
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Policy costs
POLICY_COSTS = {
    'sla_breach_credit': 350,
    'transfer_cost': 305,
    'agent_hour_cost': 165,
    'replacement_logistics': 340,
    'contact_cost': {'chat': 210, 'email': 260, 'voice': 520, 'social': 240},
    'blended_contact_cost': 290,
    'goodwill_cap': 500,
    'sla_targets_hrs': {'chat': 0.25, 'voice': 2.0, 'social': 4.0, 'email': 8.0},
}

def compute_agent_csat_with_shrinkage(df, min_n=15):
    """
    Compute empirical-Bayes shrunk CSAT per agent.
    Agents with fewer than min_n responses get shrunk heavily toward the grand mean.
    Returns DataFrame with agent_id, raw_mean, shrunk_mean, n_responses, ci_lower, ci_upper.
    """
    has_csat = df[df['csat_score'].notna()].copy()
    grand_mean = has_csat['csat_score'].mean()
    grand_var = has_csat['csat_score'].var()
    
    agent_stats = has_csat.groupby('agent_id').agg(
        raw_mean=('csat_score', 'mean'),
        n_responses=('csat_score', 'count'),
        agent_var=('csat_score', 'var')
    ).reset_index()
    
    # Fill NaN variance (agents with 1 response)
    agent_stats['agent_var'] = agent_stats['agent_var'].fillna(grand_var)
    
    # Empirical Bayes shrinkage: shrunk = (n * agent_mean + k * grand_mean) / (n + k)
    # where k = grand_var / between-agent-var
    between_var = max(agent_stats['raw_mean'].var() - (grand_var / agent_stats['n_responses']).mean(), 0.01)
    k = grand_var / between_var
    
    agent_stats['shrunk_mean'] = (
        agent_stats['n_responses'] * agent_stats['raw_mean'] + k * grand_mean
    ) / (agent_stats['n_responses'] + k)
    
    # Confidence intervals (using t-distribution)
    agent_stats['ci_lower'] = agent_stats.apply(
        lambda r: r['raw_mean'] - stats.t.ppf(0.975, max(r['n_responses']-1, 1)) * 
                  np.sqrt(r['agent_var'] / r['n_responses']) if r['n_responses'] >= 2 else np.nan,
        axis=1
    )
    agent_stats['ci_upper'] = agent_stats.apply(
        lambda r: r['raw_mean'] + stats.t.ppf(0.975, max(r['n_responses']-1, 1)) * 
                  np.sqrt(r['agent_var'] / r['n_responses']) if r['n_responses'] >= 2 else np.nan,
        axis=1
    )
    
    agent_stats['sufficient_n'] = agent_stats['n_responses'] >= min_n
    agent_stats['grand_mean'] = grand_mean
    
    return agent_stats


def bootstrap_rank_stability(df, n_boot=1000, metric='shrunk_mean', bottom_n=10, top_n=5, min_n=15):
    """
    Bootstrap resample CSAT scores and re-rank agents.
    Returns how often each agent appears in bottom_n / top_n across bootstrap samples.
    """
    has_csat = df[df['csat_score'].notna()].copy()
    agents = has_csat['agent_id'].unique()
    
    bottom_counts = defaultdict(int)
    top_counts = defaultdict(int)
    
    for _ in range(n_boot):
        # Resample with replacement within each agent
        boot_sample = has_csat.groupby('agent_id').apply(
            lambda x: x.sample(n=len(x), replace=True)
        ).reset_index(drop=True)
        
        boot_stats = compute_agent_csat_with_shrinkage(boot_sample, min_n=min_n)
        boot_stats = boot_stats[boot_stats['sufficient_n']]
        
        if len(boot_stats) >= bottom_n:
            bottom = boot_stats.nsmallest(bottom_n, metric)['agent_id'].values
            for a in bottom:
                bottom_counts[a] += 1
        
        if len(boot_stats) >= top_n:
            top = boot_stats.nlargest(top_n, metric)['agent_id'].values
            for a in top:
                top_counts[a] += 1
    
    bottom_stability = {a: c/n_boot for a, c in bottom_counts.items()}
    top_stability = {a: c/n_boot for a, c in top_counts.items()}
    
    return bottom_stability, top_stability


def case_mix_adjustment(df, min_n=15):
    """
    Adjust CSAT for case-mix: channel, category, priority, product family, 
    transfers, sla_breach, tier, auto_closed.
    Uses OLS residuals approach.
    """
    has_csat = df[df['csat_score'].notna()].copy()
    
    # Encode categorical variables
    cat_vars = []
    for col in ['channel', 'category', 'priority', 'family', 'assigned_team']:
        if col in has_csat.columns:
            dummies = pd.get_dummies(has_csat[col], prefix=col, drop_first=True)
            cat_vars.append(dummies)
    
    # Numeric vars
    num_vars = []
    for col in ['transfers', 'sla_breach', 'auto_closed', 'is_repeat']:
        if col in has_csat.columns:
            num_vars.append(has_csat[[col]].fillna(0).astype(float))
    
    if not cat_vars and not num_vars:
        return compute_agent_csat_with_shrinkage(df, min_n)
    
    X_parts = cat_vars + num_vars
    X = pd.concat(X_parts, axis=1).fillna(0).astype(float)
    y = has_csat['csat_score'].values.astype(float)
    
    # OLS without agent dummies to get residuals
    from numpy.linalg import lstsq
    X_mat = np.column_stack([np.ones(len(X)), X.values])
    
    try:
        beta, _, _, _ = lstsq(X_mat, y, rcond=None)
        predicted = X_mat @ beta
        residuals = y - predicted
    except Exception:
        residuals = y - y.mean()
        predicted = np.full_like(residuals, y.mean(), dtype=float)
    
    # Adjusted CSAT = grand_mean + residual
    grand_mean = y.mean()
    has_csat = has_csat.copy()
    has_csat['adjusted_csat'] = grand_mean + residuals
    
    # Now compute agent stats on adjusted CSAT
    agent_adj = has_csat.groupby('agent_id').agg(
        adjusted_mean=('adjusted_csat', 'mean'),
        raw_mean=('csat_score', 'mean'),
        n_responses=('csat_score', 'count'),
        agent_var=('adjusted_csat', 'var')
    ).reset_index()
    
    agent_adj['agent_var'] = agent_adj['agent_var'].fillna(has_csat['adjusted_csat'].var())
    
    # Shrinkage on adjusted
    between_var = max(agent_adj['adjusted_mean'].var() - (has_csat['adjusted_csat'].var() / agent_adj['n_responses']).mean(), 0.01)
    k = has_csat['adjusted_csat'].var() / between_var
    
    agent_adj['shrunk_adjusted'] = (
        agent_adj['n_responses'] * agent_adj['adjusted_mean'] + k * grand_mean
    ) / (agent_adj['n_responses'] + k)
    
    agent_adj['ci_lower'] = agent_adj.apply(
        lambda r: r['adjusted_mean'] - stats.t.ppf(0.975, max(r['n_responses']-1, 1)) * 
                  np.sqrt(r['agent_var'] / r['n_responses']) if r['n_responses'] >= 2 else np.nan,
        axis=1
    )
    agent_adj['ci_upper'] = agent_adj.apply(
        lambda r: r['adjusted_mean'] + stats.t.ppf(0.975, max(r['n_responses']-1, 1)) * 
                  np.sqrt(r['agent_var'] / r['n_responses']) if r['n_responses'] >= 2 else np.nan,
        axis=1
    )
    
    agent_adj['sufficient_n'] = agent_adj['n_responses'] >= min_n
    agent_adj['grand_mean'] = grand_mean
    
    # Variance explained by case-mix
    ss_total = np.sum((y - y.mean())**2)
    ss_explained = np.sum((predicted - y.mean())**2)
    r_squared = ss_explained / ss_total if ss_total > 0 else 0
    
    return agent_adj, r_squared, has_csat


def hypothesis_testing(df, products_df):
    """
    Test competing explanations for CSAT slide.
    Returns dict of findings with Rs impact.
    """
    results = {}
    
    # Time periods
    df = df.copy()
    df['created_dt'] = pd.to_datetime(df['created_at'])
    df['month'] = df['created_dt'].dt.to_period('M')
    
    pre = df[df['created_dt'] < '2025-10-01']
    festive = df[(df['created_dt'] >= '2025-10-01') & (df['created_dt'] < '2026-01-01')]
    post = df[df['created_dt'] >= '2026-01-01']
    
    # Overall CSAT trend
    for period_name, period_df in [('Pre-festive', pre), ('Festive', festive), ('Post-festive', post)]:
        csat_vals = period_df['csat_score'].dropna()
        results[f'csat_{period_name}'] = {
            'mean': csat_vals.mean(),
            'n': len(csat_vals),
            'total_tickets': len(period_df)
        }
    
    # H1: Agent skill - how much variance is agent-level after adjustment?
    # (computed separately in case_mix_adjustment)
    
    # H2: Transfers and misrouting
    transferred = df[df['transfers'] > 0]
    not_transferred = df[df['transfers'] == 0]
    t2_csat = transferred['csat_score'].dropna()
    nt_csat = not_transferred['csat_score'].dropna()
    transfer_cost_total = transferred['transfers'].sum() * POLICY_COSTS['transfer_cost']
    results['H2_transfers'] = {
        'transferred_tickets': len(transferred),
        'transfer_csat': t2_csat.mean() if len(t2_csat) > 0 else None,
        'no_transfer_csat': nt_csat.mean() if len(nt_csat) > 0 else None,
        'total_transfer_cost_rs': transfer_cost_total,
        'quarterly_cost_rs': transfer_cost_total / 6 * 1  # approx quarterly
    }
    
    # H3: First-response breaches
    if 'sla_breach' in df.columns:
        breached = df[df['sla_breach'] == 1]
        not_breached = df[df['sla_breach'] == 0]
        b_csat = breached['csat_score'].dropna()
        nb_csat = not_breached['csat_score'].dropna()
        breach_credit_total = len(breached) * POLICY_COSTS['sla_breach_credit']
        
        # Breach by period
        breach_by_period = {}
        for pname, pdf in [('Pre-festive', pre), ('Festive', festive), ('Post-festive', post)]:
            if 'sla_breach' in pdf.columns:
                breach_by_period[pname] = pdf['sla_breach'].mean() if len(pdf) > 0 else 0
        
        results['H3_breaches'] = {
            'breached_tickets': len(breached),
            'breach_rate': len(breached) / len(df),
            'breach_csat': b_csat.mean() if len(b_csat) > 0 else None,
            'no_breach_csat': nb_csat.mean() if len(nb_csat) > 0 else None,
            'total_breach_credit_rs': breach_credit_total,
            'breach_by_period': breach_by_period
        }
    
    # H4: Product defects (Pulse 2 specifically)
    pl2 = df[df['product_sku'] == 'VA-EB-PL2']
    other = df[df['product_sku'] != 'VA-EB-PL2']
    pl2_csat = pl2['csat_score'].dropna()
    other_csat = other['csat_score'].dropna()
    
    # Replacement cost for PL2
    if 'unit_cost_inr' in df.columns:
        pl2_repl = pl2[pl2['replacement_issued'] == 'Y']
        pl2_repl_cost = len(pl2_repl) * (1480 + 340)  # PL2 unit cost + logistics
    else:
        pl2_repl = pl2[pl2['replacement_issued'] == 'Y']
        pl2_repl_cost = len(pl2_repl) * (1480 + 340)
    
    results['H4_product_defect'] = {
        'pl2_tickets': len(pl2),
        'pl2_replacements': len(pl2_repl),
        'pl2_csat': pl2_csat.mean() if len(pl2_csat) > 0 else None,
        'other_csat': other_csat.mean() if len(other_csat) > 0 else None,
        'pl2_replacement_cost_rs': pl2_repl_cost,
        'pl2_share_of_all_tickets': len(pl2) / len(df),
    }
    
    # H5: Repeat contacts
    if 'is_repeat' in df.columns:
        repeats = df[df['is_repeat'] == True]
        repeat_cost = 0
        for ch, cost in POLICY_COSTS['contact_cost'].items():
            repeat_cost += len(repeats[repeats['channel'] == ch]) * cost
        results['H5_repeats'] = {
            'repeat_tickets': len(repeats),
            'repeat_rate': len(repeats) / len(df),
            'repeat_cost_rs': repeat_cost,
        }
    
    # H6: Data artefacts
    legacy = df[df['source_system'] == 'legacy_fd']
    results['H6_data'] = {
        'legacy_tickets': len(legacy),
        'legacy_pct': len(legacy) / len(df),
    }
    
    return results


def compute_handle_time_stats(df, tier_col='tier'):
    """
    Compute handle time per agent, separated by tier.
    Tier 2 measured in days, Tier 1 in hours.
    """
    resolved = df[df['status'].isin(['resolved', 'closed'])].copy()
    resolved = resolved[resolved['handle_time_hrs'].notna() & (resolved['handle_time_hrs'] >= 0)]
    
    agent_handle = resolved.groupby(['agent_id', tier_col]).agg(
        mean_handle_hrs=('handle_time_hrs', 'mean'),
        median_handle_hrs=('handle_time_hrs', 'median'),
        n_resolved=('ticket_id', 'count'),
        handle_std=('handle_time_hrs', 'std')
    ).reset_index()
    
    agent_handle['handle_std'] = agent_handle['handle_std'].fillna(0)
    agent_handle['ci_lower'] = agent_handle['mean_handle_hrs'] - 1.96 * agent_handle['handle_std'] / np.sqrt(agent_handle['n_resolved'])
    agent_handle['ci_upper'] = agent_handle['mean_handle_hrs'] + 1.96 * agent_handle['handle_std'] / np.sqrt(agent_handle['n_resolved'])
    
    return agent_handle


def identify_hardware_rota(df, agents_df):
    """
    Identify Kavya's hardware triage rota (4 agents) and the warranty team.
    
    Kavya Pandey = A3006 (Chat Frontline).
    The 'hardware triage rota' = agents who disproportionately handle hardware categories
    (Warranty & Repair, Charging & Battery, Connectivity, Audio Quality) in Chat Frontline.
    """
    # Kavya is A3006
    kavya_id = 'A3006'
    
    # Hardware categories
    hw_cats = ['Warranty & Repair', 'Charging & Battery', 'Connectivity', 'Audio Quality']
    
    # Chat Frontline agents
    chat_agents = agents_df[agents_df['team'] == 'Chat Frontline']['agent_id'].values
    
    # For each chat frontline agent, compute fraction of tickets in hardware categories
    chat_tickets = df[df['agent_id'].isin(chat_agents)]
    agent_hw_frac = chat_tickets.groupby('agent_id').apply(
        lambda x: (x['category'].isin(hw_cats)).mean()
    ).reset_index()
    agent_hw_frac.columns = ['agent_id', 'hw_fraction']
    agent_hw_frac = agent_hw_frac.sort_values('hw_fraction', ascending=False)
    
    # Top 4 by hardware fraction = the rota
    hw_rota = agent_hw_frac.head(4)['agent_id'].values
    
    # Warranty team = Escalations & Warranty (tier 2)
    warranty_team = agents_df[agents_df['team'] == 'Escalations & Warranty']['agent_id'].values
    
    return {
        'kavya_id': kavya_id,
        'hw_rota': hw_rota,
        'warranty_team': warranty_team,
        'hw_fractions': agent_hw_frac
    }


def text_classifier(df, n_hand_label=100):
    """
    Simple keyword/rule-based root cause classifier for customer messages.
    Categories: product_defect, delivery, billing, how_to, misrouted, warranty, other
    """
    rules = {
        'product_defect': [
            r'not working', r'broken', r'defect', r'dead', r'no sound', r'stopped',
            r'battery.*drain', r'battery.*die', r'battery.*drop', r'charging.*issue',
            r'won.t charge', r'won.t turn on', r'won.t connect', r'crackling',
            r'buzzing', r'static', r'one side', r'left.*ear', r'right.*ear',
            r'pairing.*fail', r'disconnect', r'audio.*cut', r'DOA', r'dead on arrival'
        ],
        'delivery': [
            r'not delivered', r'not received', r'haven.t received', r'where is my order',
            r'tracking', r'shipping', r'dispatch', r'courier', r'lost in transit',
            r'wrong address', r'delivery.*delay', r'still waiting'
        ],
        'billing': [
            r'refund', r'charged twice', r'duplicate.*payment', r'wrong amount',
            r'invoice', r'payment.*fail', r'coupon', r'discount', r'price',
            r'overcharged', r'money back'
        ],
        'how_to': [
            r'how to', r'how do', r'setup', r'set up', r'pair', r'connect.*to',
            r'compatible', r'work with', r'app.*install', r'firmware.*update',
            r'instructions', r'tutorial', r'guide'
        ],
        'warranty': [
            r'warranty', r'RMA', r'replacement', r'repair', r'claim',
            r'under warranty', r'warranty.*expired'
        ],
    }
    
    import re
    
    def classify(msg):
        if pd.isna(msg):
            return 'other'
        msg_lower = str(msg).lower()
        scores = {}
        for cat, patterns in rules.items():
            score = sum(1 for p in patterns if re.search(p, msg_lower))
            if score > 0:
                scores[cat] = score
        if scores:
            return max(scores, key=scores.get)
        return 'other'
    
    df = df.copy()
    df['root_cause'] = df['customer_message'].apply(classify)
    
    return df


if __name__ == '__main__':
    print("Analysis module loaded. Use with cleaned data from data_clean.py")
    print("Available functions:")
    print("  - compute_agent_csat_with_shrinkage(df, min_n=15)")
    print("  - bootstrap_rank_stability(df, n_boot=1000)")
    print("  - case_mix_adjustment(df, min_n=15)")
    print("  - hypothesis_testing(df, products_df)")
    print("  - compute_handle_time_stats(df)")
    print("  - identify_hardware_rota(df, agents_df)")
    print("  - text_classifier(df)")
