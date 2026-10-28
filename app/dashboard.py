"""
dashboard.py — Apple Liquid Glass Multi-Tenant Cloud Dashboard.
Features:
- User Authentication (Login & Register)
- Per-User Data Isolation
- Seamless Bank Alerts Sync (IMAP App Password or OAuth)
- Category Filter with Ledger & Statement CSV Export
- Spending Overview, Trend Charts, and Day-by-Day Timeline
- Savings & Portfolio Tracker
- money_manager config (Bank sender, Gmail connection, AI keys)
- Clean typography without text emojis
"""

import sys
import os
from datetime import date, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from database import (
    init_auth_db,
    register_user,
    authenticate_user,
    get_user_settings,
    update_user_settings,
    get_all_transactions,
    get_summary_stats,
    get_category_totals,
    get_daily_totals,
)
from categories import CATEGORIES
from sync import sync_emails_for_user

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Money Manager Cloud",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Apple "Liquid Glass" Cupertino Design System ──────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
        color: #f5f5f7;
        -webkit-font-smoothing: antialiased;
    }

    .stApp {
        background: radial-gradient(circle at 15% 15%, rgba(10, 132, 255, 0.08) 0%, transparent 45%),
                    radial-gradient(circle at 85% 25%, rgba(191, 90, 242, 0.06) 0%, transparent 40%),
                    radial-gradient(circle at 50% 80%, rgba(48, 209, 88, 0.05) 0%, transparent 50%),
                    #0b0c10;
        background-attachment: fixed;
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(28px) saturate(190%);
        -webkit-backdrop-filter: blur(28px) saturate(190%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 0.15),
                    0 16px 36px 0 rgba(0, 0, 0, 0.38);
        border-radius: 20px;
        padding: 24px 20px;
        text-align: left;
        position: relative;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .glass-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.22);
    }

    .metric-caption {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #86868b;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .metric-number {
        font-size: 2.1rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        line-height: 1.1;
        margin-bottom: 6px;
        font-feature-settings: "tnum" 1;
    }
    .metric-footnote {
        font-size: 0.75rem;
        color: #6e6e73;
        font-weight: 400;
    }

    .pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 14px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 980px;
        font-size: 0.78rem;
        font-weight: 500;
        color: #a1a1a6;
        backdrop-filter: blur(16px);
    }

    button[kind="primary"] {
        background: linear-gradient(180deg, #0A84FF 0%, #0066CC 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.35), 0 4px 14px rgba(10, 132, 255, 0.4) !important;
        border-radius: 980px !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        padding: 10px 24px !important;
        transition: all 0.25s ease !important;
    }
    button[kind="primary"]:hover {
        box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.45), 0 6px 20px rgba(10, 132, 255, 0.6) !important;
        transform: scale(1.01) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 6px;
        backdrop-filter: blur(20px);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px;
        color: #86868b;
        font-size: 0.88rem;
        font-weight: 500;
        padding: 8px 18px;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(255, 255, 255, 0.12) !important;
        color: #ffffff !important;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    [data-testid="stSidebar"] {
        background: rgba(18, 18, 22, 0.75) !important;
        backdrop-filter: blur(35px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(35px) saturate(200%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
</style>
""", unsafe_allow_html=True)

APPLE_COLORS = [
    "#0A84FF", "#5E5CE6", "#BF5AF2", "#FF375F", "#FF9F0A",
    "#30D158", "#64D2FF", "#FFD60A", "#FF6482", "#00E096",
]

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="-apple-system, SF Pro Display, sans-serif", color="#86868b", size=12),
    margin=dict(t=30, b=30, l=30, r=30),
)

init_auth_db()

# ── Session State Management ──────────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None

today = date.today()
if "start_date" not in st.session_state:
    st.session_state.start_date = today.replace(day=1)
if "end_date" not in st.session_state:
    st.session_state.end_date = today
if "selected_category" not in st.session_state:
    st.session_state.selected_category = "All"


# ── Authentication View (When Logged Out) ─────────────────────────────────────
if st.session_state.user is None:
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    c_mid, _ = st.columns([1.2, 1])

    with c_mid:
        st.markdown("""
        <div class="glass-card" style="padding: 32px 36px; text-align: left;">
            <div style="font-size: 1.8rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 6px;">
                Money Manager Cloud
            </div>
            <div style="color: #86868b; font-size: 0.95rem; margin-bottom: 24px;">
                AI-powered bank alert sync, spending insights & portfolio intelligence.
            </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                username_input = st.text_input("Username or Email")
                password_input = st.text_input("Password", type="password")
                submit_login = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                if submit_login:
                    user_data = authenticate_user(username_input, password_input)
                    if user_data:
                        st.session_state.user = user_data
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with tab_register:
            with st.form("register_form"):
                reg_username = st.text_input("Choose Username (min 3 chars)")
                reg_email = st.text_input("Email (Optional)")
                reg_password = st.text_input("Password (min 4 chars)", type="password")
                submit_reg = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                if submit_reg:
                    success, msg, user_id = register_user(reg_username, reg_email, reg_password)
                    if success:
                        st.success("Account created successfully! Please sign in.")
                    else:
                        st.error(msg)

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ── Authenticated User View ───────────────────────────────────────────────────
user = st.session_state.user
user_id = user["id"]
user_settings = get_user_settings(user_id)
selected_category = st.session_state.selected_category

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### **Money Manager**")
    st.markdown(
        f'<div class="pill-badge">User: <b style="color:#ffffff;">{user["username"]}</b></div>',
        unsafe_allow_html=True,
    )

    ai_prov = user_settings.get("ai_provider", "gemini")
    model_name = user_settings.get("groq_model" if ai_prov == "groq" else "gemini_model") or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    st.markdown(
        f'<div class="pill-badge" style="margin-top:6px;">Engine: <b style="color:#ffffff;">{ai_prov.title()}</b> · <span style="opacity:0.75;">{model_name}</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown("---")

    # Date Range
    st.markdown("**Date Window**")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input("From", key="start_date")
    with col_d2:
        end_date = st.date_input("To", key="end_date")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Sync Button
    sync_btn = st.button("Sync Bank Alerts", type="primary", use_container_width=True)
    sync_status = st.empty()

    if sync_btn:
        progress_bar = st.progress(0.0)

        def on_sync_progress(fraction: float, msg: str):
            progress_bar.progress(fraction)
            sync_status.caption(f"{msg}")

        try:
            res = sync_emails_for_user(
                user_id=user_id,
                start_date=str(start_date),
                end_date=str(end_date),
                progress_callback=on_sync_progress,
                max_workers=6,
            )
            progress_bar.empty()
            sync_status.empty()
            if res and res.get("inserted", 0) > 0:
                st.success(f"Synced {res['inserted']} new bank alerts!")
            else:
                st.info("Everything is already up to date.")
            st.rerun()
        except Exception as ex:
            progress_bar.empty()
            sync_status.empty()
            st.error(f"Sync error: {ex}")

    st.markdown("---")

    # Filter Data (Type only)
    st.markdown("**Filter Data**")
    selected_type = st.selectbox("Type", ["All", "debit", "credit"])

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.75rem; color:#86868b; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:8px;'>Click a category to view ledger & export:</div>", unsafe_allow_html=True)

    cat_totals = get_category_totals(user_id=user_id, start_date=str(start_date), end_date=str(end_date))

    if selected_category != "All":
        c_h1, c_h2 = st.columns([2.5, 1.2])
        with c_h1:
            st.markdown(f'<div class="pill-badge" style="margin-bottom:6px;">Category: <b style="color:#ffffff;">{selected_category}</b></div>', unsafe_allow_html=True)
        with c_h2:
            if st.button("Reset", key="sb_reset_cat", use_container_width=True):
                st.session_state.selected_category = "All"
                st.rerun()

    if cat_totals:
        dot_css_rules = []
        for idx, row in enumerate(cat_totals):
            c_color = APPLE_COLORS[idx % len(APPLE_COLORS)]
            c_name = row["category"]
            dot_css_rules.append(f"""
            div[data-testid="stSidebar"] button[aria-label*="{c_name}"] p::before {{
                content: "\\25CF  " !important;
                color: {c_color} !important;
                font-size: 1.15em !important;
                filter: drop-shadow(0 0 7px {c_color}) !important;
            }}
            """)
        st.html(f"<style>{''.join(dot_css_rules)}</style>")

        sb_cols = st.columns(2)
        for idx, row in enumerate(cat_totals):
            name = row["category"]
            is_active = (selected_category == name)
            target_col = sb_cols[idx % 2]
            with target_col:
                if st.button(name, key=f"sb_cat_btn_{name}", use_container_width=True, type="primary" if is_active else "secondary"):
                    if st.session_state.selected_category == name:
                        st.session_state.selected_category = "All"
                    else:
                        st.session_state.selected_category = name
                    st.rerun()

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if st.button("Sign Out", use_container_width=True):
        st.session_state.user = None
        st.rerun()


# ── Load User Data ────────────────────────────────────────────────────────────
txns = get_all_transactions(
    user_id=user_id,
    start_date=str(start_date),
    end_date=str(end_date),
    category="All",
    txn_type=selected_type,
)
df = pd.DataFrame(txns)

daily_totals = get_daily_totals(user_id=user_id, start_date=str(start_date), end_date=str(end_date))

# ── Summary Calculations ──────────────────────────────────────────────────────
if not df.empty:
    filter_spent = df[df["type"] == "debit"]["amount"].sum()
    filter_income = df[df["type"] == "credit"]["amount"].sum()
    filter_count = len(df)
else:
    filter_spent = filter_income = filter_count = 0

net_savings = filter_income - filter_spent
net_color = "#30D158" if net_savings >= 0 else "#FF453A"


# ── Metric Cards ──────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:#FF453A;">●</span> Total Spent</div>
        <div class="metric-number" style="color: #FF453A;">₹{filter_spent:,.2f}</div>
        <div class="metric-footnote">Outflows & debits</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:#30D158;">●</span> Total Income</div>
        <div class="metric-number" style="color: #30D158;">₹{filter_income:,.2f}</div>
        <div class="metric-footnote">Credits & deposits</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:{net_color};">●</span> Net Cashflow</div>
        <div class="metric-number" style="color: {net_color};">₹{net_savings:,.2f}</div>
        <div class="metric-footnote">Income minus expenses</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:#0A84FF;">●</span> Alerts Volume</div>
        <div class="metric-number" style="color: #0A84FF;">{filter_count}</div>
        <div class="metric-footnote">Bank emails processed</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# ── Primary Navigation Tabs ───────────────────────────────────────────────────
tab_overview, tab_timeline, tab_cats, tab_ledger, tab_portfolio, tab_settings = st.tabs([
    "Overview",
    "Day-by-Day Timeline",
    "Category Analysis",
    "Ledger & Export",
    "Savings & Portfolio",
    "money_manager config",
])


# ── Tab 1: Overview ───────────────────────────────────────────────────────────
with tab_overview:
    if not df.empty:
        col_pie, col_bar = st.columns([1, 1.2])

        with col_pie:
            if cat_totals:
                cat_df = pd.DataFrame(cat_totals)
                st.markdown("<div style='font-size:1.05rem; font-weight:600; margin-bottom:6px;'>Category Overview</div>", unsafe_allow_html=True)

                fig_pie = px.pie(
                    cat_df,
                    values="total",
                    names="category",
                    hole=0.72,
                    color_discrete_sequence=APPLE_COLORS,
                )
                fig_pie.update_traces(
                    textposition="inside",
                    textinfo="percent",
                    hovertemplate="<b>%{label}</b><br>₹%{value:,.2f} (%{percent})<extra></extra>",
                    marker=dict(line=dict(color="#0c0d12", width=2.5)),
                )
                fig_pie.update_layout(**PLOT_LAYOUT, height=360, showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No debit transactions recorded.")

        with col_bar:
            st.markdown("<b style='color:#f5f5f7; font-size:1.05rem;'>Daily Spending Trend</b>", unsafe_allow_html=True)
            if daily_totals:
                day_df = pd.DataFrame(daily_totals)
                fig_trend = px.bar(
                    day_df,
                    x="date",
                    y="total",
                    color_discrete_sequence=["#0A84FF"],
                    labels={"date": "Date", "total": "Debited (₹)"},
                )
                fig_trend.update_layout(
                    **PLOT_LAYOUT,
                    height=360,
                    xaxis=dict(showgrid=False, tickangle=-45),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("No daily spending trends available.")

        # ── Category-Filtered Ledger & Export Display ───────────────────────────
        if selected_category != "All":
            cat_txns = df[df["category"] == selected_category] if not df.empty else pd.DataFrame()
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='glass-card' style='padding: 20px 24px;'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;'>"
                f"  <span style='font-size:1.15rem; font-weight:700; color:#f5f5f7;'>Ledger & Export: <span style='color:#0A84FF;'>{selected_category}</span> ({len(cat_txns)} records)</span>"
                f"  <span class='pill-badge'>Category Filter</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            if not cat_txns.empty:
                t_cols = cat_txns[["date", "time", "type", "amount", "merchant", "category", "balance", "description"]].copy()
                t_cols.columns = ["Date", "Time", "Type", "Amount (₹)", "Merchant", "Category", "Balance (₹)", "Description"]
                t_cols["Amount (₹)"] = t_cols["Amount (₹)"].map(lambda x: f"₹{x:,.2f}")
                t_cols["Balance (₹)"] = t_cols["Balance (₹)"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) and x != "" else "—")

                def color_badge(val):
                    v = str(val).strip().lower()
                    if v == "debit":
                        return "color: #FF3B30; font-weight: 700;"
                    elif v == "credit":
                        return "color: #34C759; font-weight: 700;"
                    return ""

                styled_cat_ledger = t_cols.style.map(color_badge, subset=["Type"])
                st.dataframe(styled_cat_ledger, use_container_width=True, height=320)

                cat_csv = cat_txns.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"Download {selected_category} Statement (CSV)",
                    data=cat_csv,
                    file_name=f"{selected_category.lower().replace(' ', '_')}_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    key=f"export_cat_btn_{selected_category}",
                )
            else:
                st.info(f"No transactions found for {selected_category}.")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No transactions found for this date range. Click 'Sync Bank Alerts' in the sidebar!")


# ── Tab 2: Timeline ───────────────────────────────────────────────────────────
with tab_timeline:
    if not df.empty:
        daily_summary = df.groupby("date").apply(
            lambda g: pd.Series({
                "Debited (₹)": g[g["type"] == "debit"]["amount"].sum(),
                "Credited (₹)": g[g["type"] == "credit"]["amount"].sum(),
                "Net Flow (₹)": g[g["type"] == "credit"]["amount"].sum() - g[g["type"] == "debit"]["amount"].sum(),
                "Alerts": len(g),
            }),
            include_groups=False,
        ).reset_index().sort_values(by="date", ascending=False)

        fig_daily = go.Figure()
        fig_daily.add_trace(go.Bar(
            x=daily_summary["date"],
            y=daily_summary["Debited (₹)"],
            name="Spent (Debit)",
            marker_color="#FF453A",
        ))
        fig_daily.add_trace(go.Bar(
            x=daily_summary["date"],
            y=daily_summary["Credited (₹)"],
            name="Income (Credit)",
            marker_color="#30D158",
        ))
        fig_daily.update_layout(
            **PLOT_LAYOUT,
            barmode="group",
            height=380,
            xaxis=dict(showgrid=False, tickangle=-45),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_daily, use_container_width=True)

        d_show = daily_summary.copy()
        d_show["Debited (₹)"] = d_show["Debited (₹)"].map(lambda x: f"₹{x:,.2f}")
        d_show["Credited (₹)"] = d_show["Credited (₹)"].map(lambda x: f"₹{x:,.2f}")
        d_show["Net Flow (₹)"] = d_show["Net Flow (₹)"].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(d_show, use_container_width=True)
    else:
        st.info("No daily data recorded.")


# ── Tab 3: Category Analysis ──────────────────────────────────────────────────
with tab_cats:
    if cat_totals:
        c_df = pd.DataFrame(cat_totals)
        tot_debit = c_df["total"].sum()
        c_df["Share"] = (c_df["total"] / tot_debit * 100).map(lambda x: f"{x:.1f}%")

        c_col1, c_col2 = st.columns([1.1, 1])
        with c_col1:
            fig_hbar = px.bar(
                c_df.sort_values(by="total", ascending=True),
                x="total",
                y="category",
                orientation="h",
                color="total",
                color_continuous_scale=["#0A84FF", "#BF5AF2"],
                labels={"total": "Amount (₹)", "category": "Category"},
            )
            fig_hbar.update_layout(**PLOT_LAYOUT, coloraxis_showscale=False, height=400)
            st.plotly_chart(fig_hbar, use_container_width=True)

        with c_col2:
            c_show = c_df.copy()
            c_show["Total Spent"] = c_show["total"].map(lambda x: f"₹{x:,.2f}")
            c_show = c_show[["category", "Total Spent", "Share"]]
            c_show.columns = ["Category", "Total Spent (₹)", "Share %"]
            st.dataframe(c_show, use_container_width=True, height=380)
    else:
        st.info("No expense categories found in this period.")


# ── Tab 4: Ledger & Export ────────────────────────────────────────────────────
with tab_ledger:
    ledger_df = df.copy()
    if selected_category != "All":
        ledger_df = ledger_df[ledger_df["category"] == selected_category]
        ledger_title = f"Transaction Ledger for {selected_category} ({len(ledger_df)})"
        st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center;'><b style='color:#f5f5f7; font-size:1.05rem;'>{ledger_title}</b><span class='pill-badge'>Filtered: {selected_category}</span></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<b style='color:#f5f5f7; font-size:1.05rem;'>Transaction Ledger ({filter_count})</b>", unsafe_allow_html=True)

    if not ledger_df.empty:
        search_q = st.text_input("Search Ledger", placeholder="Filter by merchant or notes (e.g. Swiggy, Amazon)...")
        if search_q:
            mask = (
                ledger_df["merchant"].str.contains(search_q, case=False, na=False) |
                ledger_df["description"].str.contains(search_q, case=False, na=False)
            )
            ledger_df = ledger_df[mask]

        table_cols = ledger_df[["date", "time", "type", "amount", "merchant", "category", "balance", "description"]].copy()
        table_cols.columns = ["Date", "Time", "Type", "Amount (₹)", "Merchant", "Category", "Balance (₹)", "Description"]
        table_cols["Amount (₹)"] = table_cols["Amount (₹)"].map(lambda x: f"₹{x:,.2f}")
        table_cols["Balance (₹)"] = table_cols["Balance (₹)"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) and x != "" else "—")

        def color_badge(val):
            v = str(val).strip().lower()
            if v == "debit":
                return "color: #FF3B30; font-weight: 700;"
            elif v == "credit":
                return "color: #34C759; font-weight: 700;"
            return ""

        styled_ledger = table_cols.style.map(color_badge, subset=["Type"])
        st.dataframe(styled_ledger, use_container_width=True, height=420)

        csv_bytes = ledger_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Statement (CSV)",
            data=csv_bytes,
            file_name=f"statement_{user['username']}_{start_date}_{end_date}.csv",
            mime="text/csv",
        )
    else:
        st.info("No transaction ledger items to display.")


# ── Tab 5: Savings & Portfolio ────────────────────────────────────────────────
with tab_portfolio:
    cash_val = float(user_settings.get("cash_savings") or 0.0)
    pf_val = float(user_settings.get("pf_amount") or 0.0)
    gold_val = float(user_settings.get("gold_amount") or 0.0)
    mf_val = float(user_settings.get("mutual_funds") or 0.0)
    total_assets = cash_val + pf_val + gold_val + mf_val

    st.markdown(
        f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;'>"
        f"  <div>"
        f"    <b style='color:#f5f5f7; font-size:1.25rem;'>Savings & Investments Portfolio</b>"
        f"    <div style='color:#86868b; font-size:0.88rem;'>Privately stored in your dedicated database</div>"
        f"  </div>"
        f"  <div style='text-align:right;'>"
        f"    <div style='font-size:0.74rem; color:#86868b; text-transform:uppercase;'>Total Worth</div>"
        f"    <div style='font-size:1.45rem; font-weight:700; color:#30D158;'>₹{total_assets:,.2f}</div>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="glass-card"><div class="metric-caption"><span style="color:#30D158;">●</span> Cash Savings</div><div class="metric-number" style="color:#30D158;">₹{cash_val:,.2f}</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="glass-card"><div class="metric-caption"><span style="color:#0A84FF;">●</span> PF Amount</div><div class="metric-number" style="color:#0A84FF;">₹{pf_val:,.2f}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="glass-card"><div class="metric-caption"><span style="color:#FFD60A;">●</span> Gold Investments</div><div class="metric-number" style="color:#FFD60A;">₹{gold_val:,.2f}</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="glass-card"><div class="metric-caption"><span style="color:#BF5AF2;">●</span> Mutual Funds</div><div class="metric-number" style="color:#BF5AF2;">₹{mf_val:,.2f}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    with st.expander("Update Portfolio Values", expanded=False):
        with st.form("portfolio_form"):
            p_cash = st.number_input("Cash Savings (₹)", min_value=0.0, value=cash_val, step=1000.0)
            p_pf = st.number_input("PF Amount (₹)", min_value=0.0, value=pf_val, step=1000.0)
            p_gold = st.number_input("Gold Investments (₹)", min_value=0.0, value=gold_val, step=1000.0)
            p_mf = st.number_input("Mutual Funds (₹)", min_value=0.0, value=mf_val, step=1000.0)
            save_p = st.form_submit_button("Save Portfolio", type="primary")

            if save_p:
                update_user_settings(
                    user_id=user_id,
                    cash_savings=p_cash,
                    pf_amount=p_pf,
                    gold_amount=p_gold,
                    mutual_funds=p_mf,
                )
                st.success("Portfolio values updated successfully!")
                st.rerun()


# ── Tab 6: money_manager config ───────────────────────────────────────────────
with tab_settings:
    st.markdown("### **money_manager config**")
    st.markdown("<div style='color:#86868b; font-size:0.9rem; margin-bottom:16px;'>Configure your bank sender address, Gmail connection, and AI API key.</div>", unsafe_allow_html=True)

    with st.form("settings_form"):
        st.markdown("#### 1. Bank Alert Sender")
        s_bank_email = st.text_input(
            "Bank Alert Sender Email",
            value=user_settings.get("bank_email_sender") or "alerts@yourbank.com",
            help="E.g., alerts@hdfcbank.net, alerts@icicibank.com, axisbank@axisbank.com, etc."
        )

        st.markdown("#### 2. Gmail Sync Method")
        s_method = st.radio(
            "Authentication Method",
            ["Gmail App Password (Recommended & Instant)", "OAuth 2.0 Token"],
            index=0 if user_settings.get("gmail_auth_method") != "oauth" else 1,
        )

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            s_gmail_user = st.text_input(
                "Your Gmail Address",
                value=user_settings.get("gmail_address") or "",
                placeholder="your.email@gmail.com",
            )
        with col_g2:
            s_gmail_pwd = st.text_input(
                "Google 16-character App Password",
                value=user_settings.get("gmail_app_password") or "",
                type="password",
                placeholder="xxxx xxxx xxxx xxxx",
                help="Generate at: https://myaccount.google.com/apppasswords"
            )

        st.caption("To create a Google App Password: Go to https://myaccount.google.com/apppasswords -> Sign in -> Type 'Money Manager' -> Copy the 16 letters here.")

        s_oauth_json = st.text_area(
            "OAuth 2.0 Token JSON (Only needed if using OAuth method)",
            value=user_settings.get("gmail_token_json") or "",
            placeholder='{"token": "ya29...", "refresh_token": "..."}',
            height=80,
        )

        st.markdown("#### 3. AI Parser Configuration")
        col_ai1, col_ai2 = st.columns(2)
        with col_ai1:
            s_provider = st.selectbox(
                "AI Provider",
                ["gemini", "groq"],
                index=0 if user_settings.get("ai_provider") != "groq" else 1,
            )
        with col_ai2:
            s_gemini_key = st.text_input(
                "Gemini API Key",
                value=user_settings.get("gemini_api_key") or "",
                type="password",
                help="Get a key from https://aistudio.google.com/apikey",
            )

        s_groq_key = st.text_input(
            "Groq API Key (if using Groq)",
            value=user_settings.get("groq_api_key") or "",
            type="password",
            help="Get a free key from https://console.groq.com/keys",
        )

        save_settings_btn = st.form_submit_button("Save All Settings", type="primary")

        if save_settings_btn:
            chosen_method = "oauth" if "OAuth" in s_method else "app_password"
            update_user_settings(
                user_id=user_id,
                bank_email_sender=s_bank_email,
                gmail_auth_method=chosen_method,
                gmail_address=s_gmail_user,
                gmail_app_password=s_gmail_pwd,
                gmail_token_json=s_oauth_json,
                ai_provider=s_provider,
                gemini_api_key=s_gemini_key,
                groq_api_key=s_groq_key,
            )
            st.success("Settings saved successfully!")
            st.rerun()


# ── Minimal Apple Footer ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #6e6e73; font-size: 0.78rem; padding: 12px 0;'>"
    f"Money Manager Cloud &nbsp;•&nbsp; Multi-Tenant Edition &nbsp;•&nbsp; Scale to Zero"
    f"</div>",
    unsafe_allow_html=True,
)
