"""
Vireo Audio CSAT Dashboard
Streamlit application for agent performance analysis.
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_clean import load_clean_data, POLICY_COSTS
from analysis import (
    compute_agent_csat_with_shrinkage,
    bootstrap_rank_stability,
    case_mix_adjustment,
    hypothesis_testing,
    compute_handle_time_stats,
    identify_hardware_rota,
    text_classifier
)

st.set_page_config(
    page_title="Vireo Audio – CSAT Dashboard",
    page_icon="🎧",
    layout="wide"
)

@st.cache_data
def load_data():
    data = load_clean_data()
    return data

@st.cache_data
def run_analysis(tickets_json, agents_json, products_json):
    """Run all analysis. Cached to avoid recomputation."""
    tickets = pd.read_json(tickets_json)
    agents = pd.read_json(agents_json)
    products = pd.read_json(products_json)
    
    # Tier 1 and Tier 2 separately
    t1 = tickets[tickets['tier'] == 1]
    t2 = tickets[tickets['tier'] == 2]
    
    # Raw CSAT rankings
    raw_stats = compute_agent_csat_with_shrinkage(tickets, min_n=15)
    raw_t1 = compute_agent_csat_with_shrinkage(t1, min_n=15)
    raw_t2 = compute_agent_csat_with_shrinkage(t2, min_n=15)
    
    # Case-mix adjusted
    adj_stats, r_squared, adj_tickets = case_mix_adjustment(tickets, min_n=15)
    adj_t1, r2_t1, _ = case_mix_adjustment(t1, min_n=15)
    
    # Handle time
    handle_stats = compute_handle_time_stats(tickets)
    
    # Hardware rota
    hw_rota = identify_hardware_rota(tickets, agents)
    
    # Hypotheses
    hyp_results = hypothesis_testing(tickets, products)
    
    # Bootstrap stability (reduce iterations for speed)
    bottom_stab, top_stab = bootstrap_rank_stability(tickets, n_boot=500, min_n=15)
    bottom_stab_t1, top_stab_t1 = bootstrap_rank_stability(t1, n_boot=500, min_n=15)
    
    return {
        'raw_stats': raw_stats,
        'raw_t1': raw_t1,
        'raw_t2': raw_t2,
        'adj_stats': adj_stats,
        'adj_t1': adj_t1,
        'r_squared': r_squared,
        'r2_t1': r2_t1,
        'handle_stats': handle_stats,
        'hw_rota': hw_rota,
        'hyp_results': hyp_results,
        'bottom_stab': bottom_stab,
        'top_stab': top_stab,
        'bottom_stab_t1': bottom_stab_t1,
        'top_stab_t1': top_stab_t1,
        'n_total': len(tickets),
    }


@st.cache_data
def filtered_stats(tickets_json, min_n=15):
    """Recompute raw + case-mix-adjusted CSAT on a filtered ticket set.
    Bootstrap (P(bottom-10)) is skipped on filtered views for speed; only the
    default full view shows those numbers."""
    tdf = pd.read_json(tickets_json)
    raw = compute_agent_csat_with_shrinkage(tdf, min_n=min_n)
    adj, r2, _ = case_mix_adjustment(tdf, min_n=min_n)
    return raw, adj, r2


def main():
    st.title("🎧 Vireo Audio – Agent CSAT & Handle Time Dashboard")
    st.caption("Data: Jan 2025 – Jun 2026 | Policy v3.2 | Run cost: Rs 0 (no API calls)")
    
    # Load data
    with st.spinner("Loading and cleaning data..."):
        data = load_data()
    
    tickets = data['tickets']
    agents = data['agents']
    products = data['products']
    customers = data['customers']
    
    # Serialize for caching
    with st.spinner("Running analysis (first load only)..."):
        results = run_analysis(
            tickets.to_json(),
            agents.to_json(),
            products.to_json()
        )
    
    # ── Sidebar ──
    st.sidebar.header("Filters")
    tier_filter = st.sidebar.radio("Tier", ["All", "Tier 1 only", "Tier 2 only"], index=1)
    team_filter = st.sidebar.multiselect("Team", sorted(agents['team'].dropna().unique().tolist()), default=[])
    channel_filter = st.sidebar.multiselect("Channel", sorted(tickets['channel'].dropna().unique().tolist()), default=[])
    category_filter = st.sidebar.multiselect("Category", sorted(tickets['category'].dropna().unique().tolist()), default=[])
    view = st.sidebar.radio("View", ["Agent Rankings", "CSAT Trends", "Hypothesis Testing", "Handle Time", "Data Quality"])

    # Apply filters to the working ticket set
    tfilt = tickets.copy()
    if team_filter:
        tfilt = tfilt[tfilt['team_roster'].isin(team_filter)]
    if channel_filter:
        tfilt = tfilt[tfilt['channel'].isin(channel_filter)]
    if category_filter:
        tfilt = tfilt[tfilt['category'].isin(category_filter)]
    if tier_filter == "Tier 1 only":
        tfilt = tfilt[tfilt['tier'] == 1]
    elif tier_filter == "Tier 2 only":
        tfilt = tfilt[tfilt['tier'] == 2]

    # Headline KPIs (visible immediately)
    overall_csat = tfilt['csat_score'].mean()
    overall_aht = tfilt.loc[tfilt['status'].isin(['resolved', 'closed']), 'handle_time_hrs'].median()
    rated_pct = tfilt['csat_score'].notna().mean()
    stab = results['bottom_stab_t1'] if tier_filter == "Tier 1 only" else results['bottom_stab']
    n_flagged = sum(1 for v in stab.values() if v > 0.5)
    late = tfilt[tfilt['created_dt'] >= pd.Timestamp('2026-04-01')]
    late_rate = (late['replacement_issued'] == 'Y').mean() if len(late) else float('nan')

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Overall CSAT", f"{overall_csat:.2f}")
    c2.metric("Overall AHT (median)", f"{overall_aht:.2f} h")
    c3.metric("Total tickets", f"{len(tfilt):,}")
    c4.metric("Rated-response %", f"{rated_pct:.0%}")
    c5.metric("Bottom-10 flagged", f"{n_flagged}")
    c6.metric("Repl. rate (Apr-Jun 26)", f"{late_rate*1000:.0f}/1000" if pd.notna(late_rate) else "n/a")
    st.caption("Ranking: blank CSAT excluded from means; Overall AHT = median hours first_response -> resolution; replacement rate = share of Apr-Jun 2026 tickets with replacement_issued='Y'.")
    st.divider()

    # Agent name lookup
    agent_names = agents.drop_duplicates('agent_id').set_index('agent_id')['name'].to_dict()
    agent_teams = agents.drop_duplicates('agent_id').set_index('agent_id')['team'].to_dict()

    queue_filtered = bool(team_filter or channel_filter or category_filter) or tier_filter != "Tier 1 only"

    if view == "Agent Rankings":
        render_rankings(results, agent_names, agent_teams, tier_filter, tfilt, queue_filtered)
    elif view == "CSAT Trends":
        render_trends(tfilt, agent_names)
    elif view == "Hypothesis Testing":
        render_hypotheses(results, tfilt, products, agent_names)
    elif view == "Handle Time":
        render_handle_time(results, agent_names, agent_teams, tier_filter)
    elif view == "Data Quality":
        render_data_quality(tickets, data)


def render_rankings(results, agent_names, agent_teams, tier_filter, tickets_active, queue_filtered):
    st.header("Agent CSAT Rankings")

    if queue_filtered:
        raw, adj, r2 = filtered_stats(tickets_active.to_json())
        bottom_stab = top_stab = {}
        filtered_note = True
    else:
        if tier_filter == "Tier 1 only":
            raw = results['raw_t1']; adj = results['adj_t1']
            bottom_stab = results['bottom_stab_t1']; top_stab = results['top_stab_t1']
            r2 = results['r2_t1']
        elif tier_filter == "Tier 2 only":
            raw = results['raw_t2']; adj = results.get('adj_stats', results['raw_t2'])
            bottom_stab = results['bottom_stab']; top_stab = results['top_stab']
            r2 = results['r_squared']
        else:
            raw = results['raw_stats']; adj = results['adj_stats']
            bottom_stab = results['bottom_stab']; top_stab = results['top_stab']
            r2 = results['r_squared']
        filtered_note = False
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Overall CSAT", f"{raw['grand_mean'].iloc[0]:.2f}")
    with col2:
        st.metric("Agents with ≥15 responses", f"{raw['sufficient_n'].sum()}")
    with col3:
        st.metric("Case-mix R²", f"{r2:.1%}" if isinstance(r2, float) else "N/A")
    with col4:
        hw_rota = results['hw_rota']
        st.metric("Hardware rota agents", f"{len(hw_rota['hw_rota'])}")
    
    st.info(f"📊 **Case-mix adjustment** removes {r2:.1%} of CSAT variance explained by channel, category, priority, product, team, transfers, SLA breaches, and repeat contacts. The remaining variance is more attributable to agents." if isinstance(r2, float) else "")
    
    # Prepare display table
    if 'shrunk_adjusted' in adj.columns:
        display = adj.copy()
        display['rank_metric'] = display['shrunk_adjusted']
    else:
        display = raw.copy()
        display['rank_metric'] = display['shrunk_mean']
    
    display['agent_name'] = display['agent_id'].map(agent_names)
    display['team'] = display['agent_id'].map(agent_teams)
    display['bottom_10_stability'] = display['agent_id'].map(bottom_stab).fillna(0)
    display['top_5_stability'] = display['agent_id'].map(top_stab).fillna(0)
    
    # Flag hardware rota
    hw_ids = set(results['hw_rota']['hw_rota'])
    wty_ids = set(results['hw_rota']['warranty_team'])
    display['hw_rota'] = display['agent_id'].isin(hw_ids)
    display['warranty_team'] = display['agent_id'].isin(wty_ids)
    
    # Sort by rank metric
    display = display.sort_values('rank_metric', ascending=True)
    display['rank'] = range(1, len(display) + 1)
    


    # Retraining recommendation/status (categorical, uses existing signals)

    def recommendation(row):

        if row.get('warranty_team', False):

            return "Do NOT retrain - investigate warranty queue/case mix"

        if row.get('hw_rota', False):

            return "Hold - investigate hardware-triage rota exposure"

        if row['n_responses'] < 15:

            return "Insufficient evidence"

        b10 = row.get('bottom_10_stability')

        raw = row.get('raw_mean')

        adj = row.get('rank_metric')

        if pd.notna(raw) and pd.notna(adj) and (raw - adj) > 0.3:

            return "Hold - low CSAT mostly case-mix explained"

        if pd.notna(b10) and b10 > 0.8:

            return "Individual retraining candidate (stable low CSAT)"

        if pd.notna(b10) and b10 > 0.5:

            return "Watchlist - moderate confidence"

        return "Individual signal weak - further review"



    display['recommendation'] = display.apply(recommendation, axis=1)



    # Supporting evidence: volume and median AHT per agent (same tickets)

    vol = tickets_active.groupby('agent_id').size().rename('volume')

    aht = (tickets_active[tickets_active['status'].isin(['resolved', 'closed'])]

           .groupby('agent_id')['handle_time_hrs'].median().rename('aht_median_hrs'))

    display = display.merge(vol, on='agent_id', how='left').merge(aht, on='agent_id', how='left')



    # Confidence indicator

    def confidence_label(row):

        if row['n_responses'] < 15:

            return "Low sample"

        b10 = row.get('bottom_10_stability')

        if pd.notna(b10) and b10 > 0.8:

            return "High confidence bottom"

        if pd.notna(b10) and b10 > 0.5:

            return "Moderate confidence bottom"

        t5 = row.get('top_5_stability')

        if pd.notna(t5) and t5 > 0.8:

            return "High confidence top"

        if pd.notna(t5) and t5 > 0.5:

            return "Moderate confidence top"

        return "Middle"



    display['confidence'] = display.apply(confidence_label, axis=1)



    # Bottom 10

    st.subheader("Bottom 10 — Adjusted-CSAT Cohort (read the recommendation column)")

    bottom10 = display[display['sufficient_n']].head(10)



    if filtered_note:

        st.info("Filters are active, so the ranking stats above are recomputed on the filtered set; bootstrap P(bottom-10) is shown from the default view only.")



    st.dataframe(

        bottom10[['rank', 'agent_id', 'agent_name', 'team', 'volume', 'n_responses',

                   'raw_mean', 'rank_metric', 'ci_lower', 'ci_upper', 'aht_median_hrs',

                   'bottom_10_stability', 'hw_rota', 'warranty_team', 'recommendation', 'confidence']].rename(columns={

            'rank_metric': 'Adjusted CSAT (shrunk)',

            'raw_mean': 'Raw CSAT',

            'n_responses': 'Rated tickets',

            'volume': 'Ticket volume',

            'ci_lower': 'CI lower',

            'ci_upper': 'CI upper',

            'aht_median_hrs': 'AHT median (h)',

            'bottom_10_stability': 'P(bottom 10)',

            'hw_rota': 'HW triage rota',

            'warranty_team': 'Warranty team',

            'recommendation': 'Recommendation',

            'confidence': 'Confidence'

        }).style.format({

            'Raw CSAT': '{:.2f}',

            'Adjusted CSAT (shrunk)': '{:.2f}',

            'CI lower': '{:.2f}',

            'CI upper': '{:.2f}',

            'AHT median (h)': '{:.2f}',

            'P(bottom 10)': '{:.0%}',

        }),

        use_container_width=True,

        hide_index=True

    )



    wty_in_bottom = int(bottom10['warranty_team'].sum())

    rota_in_bottom = int(bottom10['hw_rota'].sum())

    st.warning(

        f"Defensibility check: {wty_in_bottom} of the 10 lowest-adjusted-CSAT agents are in the Escalations & Warranty team and {rota_in_bottom} are in the four-agent hardware-triage rota. "

        "This bottom-10 is an adjusted-CSAT performance signal, **not a retraining list**. Concentration in one queue suggests a workflow/case-mix issue (see Hypothesis Testing - Pulse 2 defect) "

        "that should be investigated before training budget is allocated. Only rows marked 'Individual retraining candidate' with stable P(bottom-10), adequate rated volume, and no queue flag should be treated as individuals to retrain."

    )



    st.subheader("CSAT vs Handle Time by Agent")

    sc = display[display['sufficient_n']].copy()

    sc['label'] = sc['agent_name'] + " (" + sc['agent_id'] + ")"

    sc['queue_flag'] = np.where(sc['warranty_team'], 'Warranty team', np.where(sc['hw_rota'], 'HW-triage rota', 'Other'))

    fig_sc = px.scatter(

        sc, x='aht_median_hrs', y='rank_metric', size='volume', color='queue_flag',

        hover_name='label', hover_data={'n_responses': True, 'bottom_10_stability': True, 'confidence': True},

        labels={'aht_median_hrs': 'Median AHT (hours)', 'rank_metric': 'Adjusted CSAT (shrunk)'},

    )

    fig_sc.update_layout(height=420)

    st.plotly_chart(fig_sc, use_container_width=True)



    # Top 5
    st.subheader("🏆 Top 5 (Diwali Bonus Candidates)")
    top5 = display[display['sufficient_n']].tail(5).sort_values('rank_metric', ascending=False)
    
    st.dataframe(
        top5[['rank', 'agent_id', 'agent_name', 'team', 'n_responses',
              'raw_mean', 'rank_metric', 'ci_lower', 'ci_upper',
              'top_5_stability', 'confidence']].rename(columns={
            'rank_metric': 'Adjusted CSAT (shrunk)',
            'raw_mean': 'Raw CSAT',
            'n_responses': 'N responses',
            'ci_lower': 'CI lower',
            'ci_upper': 'CI upper',
            'top_5_stability': 'P(top 5)',
            'confidence': 'Confidence'
        }).style.format({
            'Raw CSAT': '{:.2f}',
            'Adjusted CSAT (shrunk)': '{:.2f}',
            'CI lower': '{:.2f}',
            'CI upper': '{:.2f}',
            'P(top 5)': '{:.0%}',
        }),
        use_container_width=True,
        hide_index=True
    )
    
    # Chart: all agents
    st.subheader("All Agents – Adjusted CSAT with Confidence Intervals")
    fig = go.Figure()
    
    sufficient = display[display['sufficient_n']].sort_values('rank_metric')
    
    # Color by category
    colors = []
    for _, row in sufficient.iterrows():
        if row['agent_id'] in bottom10['agent_id'].values:
            colors.append('red')
        elif row['agent_id'] in top5['agent_id'].values:
            colors.append('green')
        elif row['hw_rota']:
            colors.append('orange')
        elif row['warranty_team']:
            colors.append('purple')
        else:
            colors.append('steelblue')
    
    fig.add_trace(go.Bar(
        x=[f"{r['agent_name']} ({r['agent_id']})" for _, r in sufficient.iterrows()],
        y=sufficient['rank_metric'],
        error_y=dict(
            type='data',
            symmetric=False,
            array=(sufficient['ci_upper'] - sufficient['rank_metric']).values,
            arrayminus=(sufficient['rank_metric'] - sufficient['ci_lower']).values,
        ),
        marker_color=colors,
        text=[f"n={int(r['n_responses'])}" for _, r in sufficient.iterrows()],
        textposition='outside'
    ))
    
    fig.add_hline(y=sufficient['rank_metric'].iloc[0] if len(sufficient) > 0 else 3.33, 
                  line_dash="dash", line_color="gray", annotation_text="Grand mean")
    fig.update_layout(
        xaxis_tickangle=45,
        yaxis_title="Adjusted CSAT (shrunk)",
        height=500,
        margin=dict(b=150),
        legend=dict(orientation="h")
    )
    # Add grand mean line at actual grand mean
    if len(sufficient) > 0:
        gm = display['grand_mean'].iloc[0] if 'grand_mean' in display.columns else 3.33
        fig.add_hline(y=gm, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Raw vs Adjusted comparison
    st.subheader("Raw vs Case-Mix Adjusted: Bottom 10 Overlap")
    raw_bottom = raw.sort_values('shrunk_mean').head(10)['agent_id'].tolist()
    adj_bottom = display[display['sufficient_n']].head(10)['agent_id'].tolist()
    overlap = set(raw_bottom) & set(adj_bottom)
    st.write(f"**{len(overlap)}/10** agents appear in bottom 10 under BOTH raw and adjusted rankings.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Raw Bottom 10:**")
        for a in raw_bottom:
            marker = "🔴" if a in overlap else "⚪"
            rota = " (HW rota)" if a in hw_ids else ""
            st.write(f"{marker} {agent_names.get(a, a)} ({a}){rota}")
    with col2:
        st.write("**Adjusted Bottom 10:**")
        for a in adj_bottom:
            marker = "🔴" if a in overlap else "🔵"
            rota = " (HW rota)" if a in hw_ids else ""
            st.write(f"{marker} {agent_names.get(a, a)} ({a}){rota}")


def render_trends(tickets, agent_names):
    st.header("CSAT Trends Over Time")
    
    df = tickets.copy()
    df['month'] = pd.to_datetime(df['created_at']).dt.to_period('M').astype(str)
    
    monthly = df.groupby('month').agg(
        mean_csat=('csat_score', 'mean'),
        n_responses=('csat_score', 'count'),
        total_tickets=('ticket_id', 'count'),
        replacement_rate=('replacement_issued', lambda x: (x=='Y').mean()),
        breach_rate=('sla_breach', 'mean') if 'sla_breach' in df.columns else ('ticket_id', 'count'),
    ).reset_index()
    
    # CSAT trend
    fig = make_subplots(rows=2, cols=2, subplot_titles=[
        'Mean CSAT by Month', 'Ticket Volume', 'Replacement Rate', 'Response Rate'
    ])
    
    fig.add_trace(go.Scatter(x=monthly['month'], y=monthly['mean_csat'], mode='lines+markers',
                             name='Mean CSAT', line=dict(color='steelblue')), row=1, col=1)
    fig.add_trace(go.Bar(x=monthly['month'], y=monthly['total_tickets'],
                         name='Total tickets', marker_color='lightblue'), row=1, col=2)
    
    # Replacement rate by month
    repl_monthly = df.groupby('month').apply(
        lambda x: (x['replacement_issued']=='Y').sum() / len(x) * 1000
    ).reset_index()
    repl_monthly.columns = ['month', 'rate_per_1000']
    fig.add_trace(go.Scatter(x=repl_monthly['month'], y=repl_monthly['rate_per_1000'],
                             mode='lines+markers', name='Replacements/1000', line=dict(color='red')),
                  row=2, col=1)
    
    # CSAT response rate
    resp_monthly = df.groupby('month').apply(
        lambda x: x['csat_score'].notna().mean() * 100
    ).reset_index()
    resp_monthly.columns = ['month', 'response_pct']
    fig.add_trace(go.Scatter(x=resp_monthly['month'], y=resp_monthly['response_pct'],
                             mode='lines+markers', name='Response %', line=dict(color='green')),
                  row=2, col=2)
    
    fig.update_layout(height=600, showlegend=False)
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    # Monthly median AHT trend (same timezone + median methodology as the rest of the app)
    aht_monthly = (df[df['status'].isin(['resolved', 'closed'])]
                   .groupby('month')['handle_time_hrs'].median().reset_index())
    aht_monthly.columns = ['month', 'aht_median_hrs']
    fig_aht = px.line(aht_monthly, x='month', y='aht_median_hrs', markers=True,
                      labels={'aht_median_hrs': 'Median AHT (hours)', 'month': 'Month'},
                      title='Monthly Median Handle Time')
    fig_aht.update_layout(height=360)
    st.plotly_chart(fig_aht, use_container_width=True)

    # CSAT by channel
    st.subheader("CSAT by Channel Over Time")
    channel_monthly = df.groupby(['month', 'channel'])['csat_score'].mean().reset_index()
    fig2 = px.line(channel_monthly, x='month', y='csat_score', color='channel',
                   labels={'csat_score': 'Mean CSAT', 'month': 'Month'})
    fig2.update_layout(height=400)
    st.plotly_chart(fig2, use_container_width=True)
    
    # CSAT by product
    st.subheader("CSAT by Product (Top 5)")
    top_skus = df['product_sku'].value_counts().head(5).index
    prod_monthly = df[df['product_sku'].isin(top_skus)].groupby(
        ['month', 'product_sku'])['csat_score'].mean().reset_index()
    fig3 = px.line(prod_monthly, x='month', y='csat_score', color='product_sku',
                   labels={'csat_score': 'Mean CSAT', 'month': 'Month'})
    fig3.update_layout(height=400)
    st.plotly_chart(fig3, use_container_width=True)


def render_hypotheses(results, tickets, products, agent_names):
    st.header("Why Is CSAT Sliding? Hypothesis Testing")
    
    hyp = results['hyp_results']
    
    # CSAT trend summary
    st.subheader("CSAT Trend")
    col1, col2, col3 = st.columns(3)
    for pname, col in [('Pre-festive', col1), ('Festive', col2), ('Post-festive', col3)]:
        key = f'csat_{pname}'
        if key in hyp:
            with col:
                st.metric(
                    f"{pname}",
                    f"{hyp[key]['mean']:.2f}",
                    delta=f"n={hyp[key]['n']}" 
                )
    
    # Impact table
    st.subheader("Quarterly Rs Impact by Hypothesis")
    
    impacts = []
    
    if 'H2_transfers' in hyp:
        h2 = hyp['H2_transfers']
        impacts.append({
            'Hypothesis': 'H2: Transfers & misrouting',
            'Evidence': f"CSAT: transferred={h2['transfer_csat']:.2f} vs not={h2['no_transfer_csat']:.2f}" if h2['transfer_csat'] else 'N/A',
            'Total Cost (Rs)': f"{h2['total_transfer_cost_rs']:,.0f}",
            'Quarterly (Rs)': f"{h2['quarterly_cost_rs']:,.0f}",
        })
    
    if 'H3_breaches' in hyp:
        h3 = hyp['H3_breaches']
        impacts.append({
            'Hypothesis': 'H3: SLA breaches',
            'Evidence': f"CSAT: breach={h3['breach_csat']:.2f} vs no breach={h3['no_breach_csat']:.2f}" if h3['breach_csat'] else 'N/A',
            'Total Cost (Rs)': f"{h3['total_breach_credit_rs']:,.0f}",
            'Quarterly (Rs)': f"{h3['total_breach_credit_rs']/6:,.0f}",
        })
    
    if 'H4_product_defect' in hyp:
        h4 = hyp['H4_product_defect']
        impacts.append({
            'Hypothesis': 'H4: Pulse 2 defect',
            'Evidence': f"CSAT: PL2={h4['pl2_csat']:.2f} vs others={h4['other_csat']:.2f}, {h4['pl2_replacements']} replacements" if h4['pl2_csat'] else 'N/A',
            'Total Cost (Rs)': f"{h4['pl2_replacement_cost_rs']:,.0f}",
            'Quarterly (Rs)': f"{h4['pl2_replacement_cost_rs']/6:,.0f}",
        })
    
    if 'H5_repeats' in hyp:
        h5 = hyp['H5_repeats']
        impacts.append({
            'Hypothesis': 'H5: Repeat contacts',
            'Evidence': f"{h5['repeat_tickets']} repeats ({h5['repeat_rate']:.1%} of tickets)",
            'Total Cost (Rs)': f"{h5['repeat_cost_rs']:,.0f}",
            'Quarterly (Rs)': f"{h5['repeat_cost_rs']/6:,.0f}",
        })
    
    st.dataframe(pd.DataFrame(impacts), use_container_width=True, hide_index=True)
    
    # Replacement cost arbitration
    st.subheader("Replacement Cost: Arjun vs Policy")
    st.write("""
    - **Arjun's estimate**: ~Rs 2,500 per replacement
    - **Policy formula**: unit_cost + Rs 340 logistics
    - **Actual weighted mean**: computed from products actually replaced
    """)
    
    repl_tickets = tickets[tickets['replacement_issued'] == 'Y']
    if 'unit_cost_inr' in repl_tickets.columns:
        mean_cost = (repl_tickets['unit_cost_inr'] + 340).mean()
    else:
        repl_with_prod = repl_tickets.merge(products, left_on='product_sku', right_on='sku', how='left')
        mean_cost = (repl_with_prod['unit_cost_inr'] + 340).mean()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Arjun's estimate", "Rs 2,500")
    with col2:
        st.metric("Policy-based mean", f"Rs {mean_cost:,.0f}")
    with col3:
        st.metric("Difference", f"Rs {2500 - mean_cost:,.0f}", delta="Arjun overestimates")
    
    # Hardware rota analysis
    st.subheader("Hardware Triage Rota: Queue or Person?")
    hw = results['hw_rota']
    
    st.write(f"**Hardware rota agents**: {', '.join([f'{agent_names.get(a,a)} ({a})' for a in hw['hw_rota']])}")
    st.write(f"**Warranty team (Tier 2)**: {', '.join([f'{agent_names.get(a,a)} ({a})' for a in hw['warranty_team']])}")
    
    # Compare rota vs non-rota CSAT
    rota_ids = set(hw['hw_rota'])
    raw = results['raw_stats']
    rota_stats = raw[raw['agent_id'].isin(rota_ids)]
    non_rota = raw[~raw['agent_id'].isin(rota_ids) & ~raw['agent_id'].isin(hw['warranty_team'])]
    
    adj = results['adj_stats']
    if 'shrunk_adjusted' in adj.columns:
        adj_rota = adj[adj['agent_id'].isin(rota_ids)]
        adj_non_rota = adj[~adj['agent_id'].isin(rota_ids) & ~adj['agent_id'].isin(hw['warranty_team'])]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Raw CSAT:**")
            st.write(f"- HW rota: {rota_stats['raw_mean'].mean():.2f}")
            st.write(f"- Other Tier 1: {non_rota['raw_mean'].mean():.2f}")
        with col2:
            st.write("**After case-mix adjustment:**")
            st.write(f"- HW rota: {adj_rota['shrunk_adjusted'].mean():.2f}")
            st.write(f"- Other Tier 1: {adj_non_rota['shrunk_adjusted'].mean():.2f}")
        
        gap_raw = non_rota['raw_mean'].mean() - rota_stats['raw_mean'].mean()
        gap_adj = adj_non_rota['shrunk_adjusted'].mean() - adj_rota['shrunk_adjusted'].mean()
        st.write(f"**Gap (non-rota minus rota): Raw={gap_raw:.2f}, Adjusted={gap_adj:.2f}**")
        if gap_adj < gap_raw * 0.5:
            st.success("✅ Neha is right: most of the gap is the queue, not the person. Case-mix adjustment closes >50% of the gap.")
        else:
            st.warning("⚠️ The gap persists after adjustment. Some agent-level signal remains.")


def render_handle_time(results, agent_names, agent_teams, tier_filter):
    st.header("Handle Time by Agent")
    
    handle = results['handle_stats']
    handle['agent_name'] = handle['agent_id'].map(agent_names)
    handle['team'] = handle['agent_id'].map(agent_teams)
    
    if tier_filter == "Tier 1 only":
        handle = handle[handle['tier'] == 1]
    elif tier_filter == "Tier 2 only":
        handle = handle[handle['tier'] == 2]
    
    st.info("⚠️ **Tier 2** (Escalations & Warranty) handles multi-day cases. Do NOT compare Tier 2 handle times with Tier 1.")
    
    # Sort by handle time
    handle = handle.sort_values('mean_handle_hrs', ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f"{r['agent_name']} ({r['agent_id']})" for _, r in handle.iterrows()],
        y=handle['median_handle_hrs'],
        error_y=dict(
            type='data',
            symmetric=False,
            array=(handle['ci_upper'] - handle['median_handle_hrs']).clip(lower=0).values,
            arrayminus=(handle['median_handle_hrs'] - handle['ci_lower']).clip(lower=0).values,
        ),
        marker_color=['purple' if r['tier']==2 else 'steelblue' for _, r in handle.iterrows()],
        text=[f"n={int(r['n_resolved'])}" for _, r in handle.iterrows()],
        textposition='outside'
    ))
    fig.update_layout(
        xaxis_tickangle=45,
        yaxis_title="Median Handle Time (hours)",
        height=500,
        margin=dict(b=150)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(
        handle[['agent_id', 'agent_name', 'team', 'tier', 'n_resolved',
                'mean_handle_hrs', 'median_handle_hrs', 'ci_lower', 'ci_upper']].rename(columns={
            'mean_handle_hrs': 'Mean (hrs)',
            'median_handle_hrs': 'Median (hrs)',
            'n_resolved': 'N resolved',
            'ci_lower': 'CI lower',
            'ci_upper': 'CI upper',
        }).style.format({
            'Mean (hrs)': '{:.1f}',
            'Median (hrs)': '{:.1f}',
            'CI lower': '{:.1f}',
            'CI upper': '{:.1f}',
        }),
        use_container_width=True,
        hide_index=True
    )


def render_data_quality(tickets, data):
    st.header("Data Quality & Cleaning Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total tickets", f"{len(tickets):,}")
        st.metric("Legacy (Freshdesk)", f"{(tickets['source_system']=='legacy_fd').sum():,}")
        st.metric("Current helpdesk", f"{(tickets['source_system']=='helpdesk').sum():,}")
    with col2:
        st.metric("CSAT response rate", f"{tickets['csat_score'].notna().mean():.1%}")
        st.metric("Blank CSAT", f"{tickets['csat_score'].isna().sum():,}")
        if 'auto_closed' in tickets.columns:
            st.metric("Auto-closed", f"{tickets['auto_closed'].sum():,}")
    with col3:
        if 'sla_breach' in tickets.columns:
            st.metric("SLA breaches", f"{tickets['sla_breach'].sum():,.0f}")
        st.metric("Transfers", f"{(tickets['transfers']>0).sum():,}")
        if 'policy_violation' in tickets.columns:
            st.metric("Refund+replacement violations", f"{tickets['policy_violation'].sum():,}")
    
    st.subheader("Timezone Fix Impact")
    st.write("""
    - **2,309** legacy tickets had negative handle times due to resolved_at stored in UTC
    - Fixed by adding +5:30 to legacy resolved_at timestamps
    - After fix: **0** negative handle times
    """)
    
    st.subheader("Reconciliation")
    st.write(f"""
    | Step | Count |
    |------|-------|
    | Raw tickets loaded | {len(tickets):,} |
    | Duplicate ticket IDs across systems | 0 |
    | Timezone-fixed (legacy) | {(tickets['source_system']=='legacy_fd').sum():,} |
    | Blank CSAT (excluded from means) | {tickets['csat_score'].isna().sum():,} |
    | Open/pending (no handle time) | {tickets['status'].isin(['open','pending']).sum():,} |
    | Final rows for analysis | {len(tickets):,} |
    """)


if __name__ == '__main__':
    main()
