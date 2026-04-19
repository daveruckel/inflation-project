import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from databricks import sql

st.set_page_config(
    page_title="What Did Money Used to Mean?",
    page_icon="$",
    layout="wide"
)

@st.cache_resource
def get_connection():
    return sql.connect(
        server_hostname=st.secrets["databricks"]["server_hostname"],
        http_path=st.secrets["databricks"]["http_path"],
        access_token=st.secrets["databricks"]["access_token"]
    )

@st.cache_data(ttl=3600)
def query(sql_str):
    with get_connection().cursor() as cursor:
        cursor.execute(sql_str)
        return pd.DataFrame(
            cursor.fetchall(),
            columns=[d[0] for d in cursor.description]
        )

# ── header ───────────────────────────────────────────────
st.title("What did money used to mean?")
st.caption(
    "A generational purchasing power calculator. "
    "Real CPI data from FRED. Morris County, NJ baseline expenses."
)

# ── sidebar inputs ────────────────────────────────────────
st.sidebar.header("Generation A")
a_start = st.sidebar.slider("Started working", 1950, 2020, 1950)
a_still = st.sidebar.checkbox("Still working today", value=True, key="a_still")
a_end   = st.sidebar.slider("Stopped working", 1951, 2025, 1985, disabled=a_still, key="a_end")
a_income = st.sidebar.number_input("Starting salary ($)", value=3500, step=500, key="a_inc")
a_wage  = st.sidebar.select_slider(
    "Annual wage growth",
    options=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0],
    value=3.0,
    format_func=lambda x: f"{x:.1f}%",
    key="a_wage"
)

st.sidebar.divider()

st.sidebar.header("Generation B")
b_start = st.sidebar.slider("Started working", 1950, 2020, 2000, key="b_start")
b_still = st.sidebar.checkbox("Still working today", value=True, key="b_still")
b_end   = st.sidebar.slider("Stopped working", 1951, 2025, 2025, disabled=b_still, key="b_end")
b_income = st.sidebar.number_input("Starting salary ($)", value=45000, step=500, key="b_inc")
b_wage  = st.sidebar.select_slider(
    "Annual wage growth",
    options=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0],
    value=3.0,
    format_func=lambda x: f"{x:.1f}%",
    key="b_wage"
)

# ── query gold tables ─────────────────────────────────────
a_end_year = 2025 if a_still else a_end
b_end_year = 2025 if b_still else b_end

df_a = query(f"""
    SELECT calc_year, monthly_surplus, nominal_salary, real_expenses
    FROM gold.generational_comparison
    WHERE start_year = {a_start}
    AND wage_growth_pct = {a_wage}
    AND calc_year <= {a_end_year}
    ORDER BY calc_year
""")

df_b = query(f"""
    SELECT calc_year, monthly_surplus, nominal_salary, real_expenses
    FROM gold.generational_comparison
    WHERE start_year = {b_start}
    AND wage_growth_pct = {b_wage}
    AND calc_year <= {b_end_year}
    ORDER BY calc_year
""")

# scale by actual income vs base $50k
df_a["monthly_surplus"] = df_a["monthly_surplus"] * (a_income / 50000)
df_a["nominal_salary"]  = df_a["nominal_salary"]  * (a_income / 50000)
df_b["monthly_surplus"] = df_b["monthly_surplus"] * (b_income / 50000)
df_b["nominal_salary"]  = df_b["nominal_salary"]  * (b_income / 50000)

# ── summary metrics ───────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Gen A starting surplus",
        f"${df_a['monthly_surplus'].iloc[0]:,.0f}/mo")
with col2:
    st.metric("Gen A ending surplus",
        f"${df_a['monthly_surplus'].iloc[-1]:,.0f}/mo",
        delta=f"${df_a['monthly_surplus'].iloc[-1] - df_a['monthly_surplus'].iloc[0]:,.0f}")
with col3:
    st.metric("Gen B starting surplus",
        f"${df_b['monthly_surplus'].iloc[0]:,.0f}/mo")
with col4:
    st.metric("Gen B ending surplus",
        f"${df_b['monthly_surplus'].iloc[-1]:,.0f}/mo",
        delta=f"${df_b['monthly_surplus'].iloc[-1] - df_b['monthly_surplus'].iloc[0]:,.0f}")

# ── main chart ────────────────────────────────────────────
st.subheader("Real monthly surplus or deficit — full career arc")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df_a["calc_year"],
    y=df_a["monthly_surplus"],
    name=f"Gen A ({a_start}, {a_wage:.1f}% raises)",
    line=dict(color="#1D9E75", width=2),
    fill="tozeroy",
    fillcolor="rgba(29,158,117,0.08)",
    hovertemplate="<b>%{x}</b><br>Gen A: $%{y:,.0f}/mo<extra></extra>"
))

fig.add_trace(go.Scatter(
    x=df_b["calc_year"],
    y=df_b["monthly_surplus"],
    name=f"Gen B ({b_start}, {b_wage:.1f}% raises)",
    line=dict(color="#185FA5", width=2),
    fill="tozeroy",
    fillcolor="rgba(24,95,165,0.08)",
    hovertemplate="<b>%{x}</b><br>Gen B: $%{y:,.0f}/mo<extra></extra>"
))

fig.add_hline(
    y=0,
    line_dash="dash",
    line_color="rgba(226,75,74,0.6)",
    annotation_text="break-even",
    annotation_position="bottom right"
)

fig.update_layout(
    height=400,
    margin=dict(l=0, r=0, t=20, b=0),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    yaxis=dict(
        tickprefix="$",
        tickformat=",.0f",
        gridcolor="rgba(128,128,128,0.1)"
    ),
    xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# ── worst / best moments ──────────────────────────────────
st.subheader("Career highlights")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Generation A**")
    worst_a = df_a.loc[df_a["monthly_surplus"].idxmin()]
    best_a  = df_a.loc[df_a["monthly_surplus"].idxmax()]
    st.metric("Best month",  f"${best_a['monthly_surplus']:,.0f}/mo",  f"{int(best_a['calc_year'])}")
    st.metric("Worst month", f"${worst_a['monthly_surplus']:,.0f}/mo", f"{int(worst_a['calc_year'])}")
    final_salary_a = df_a["nominal_salary"].iloc[-1]
    st.metric("Salary at career end", f"${final_salary_a:,.0f}/yr")

with col2:
    st.markdown("**Generation B**")
    worst_b = df_b.loc[df_b["monthly_surplus"].idxmin()]
    best_b  = df_b.loc[df_b["monthly_surplus"].idxmax()]
    st.metric("Best month",  f"${best_b['monthly_surplus']:,.0f}/mo",  f"{int(best_b['calc_year'])}")
    st.metric("Worst month", f"${worst_b['monthly_surplus']:,.0f}/mo", f"{int(worst_b['calc_year'])}")
    final_salary_b = df_b["nominal_salary"].iloc[-1]
    st.metric("Salary at career end", f"${final_salary_b:,.0f}/yr")

# ── annual inflation context ──────────────────────────────
st.subheader("Annual inflation context")

df_cpi = query("""
    SELECT year, avg_inflation_pct, peak_inflation_pct, purchasing_power_index
    FROM gold.annual_cpi
    ORDER BY year
""")

fig2 = go.Figure()

fig2.add_trace(go.Bar(
    x=df_cpi["year"],
    y=df_cpi["avg_inflation_pct"],
    name="Avg annual inflation",
    marker_color=[
        "#E24B4A" if v > 5 else "#EF9F27" if v > 3 else "#1D9E75"
        for v in df_cpi["avg_inflation_pct"]
    ],
    hovertemplate="<b>%{x}</b><br>Inflation: %{y:.2f}%<extra></extra>"
))

fig2.update_layout(
    height=300,
    margin=dict(l=0, r=0, t=20, b=0),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    yaxis=dict(
        ticksuffix="%",
        gridcolor="rgba(128,128,128,0.1)"
    ),
    xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified"
)

st.plotly_chart(fig2, use_container_width=True)
st.caption("Green = under 3% | Orange = 3–5% | Red = over 5%. Source: BLS CPI-U via FRED.")

# ── expense breakdown ─────────────────────────────────────
st.subheader("Monthly expenses at career start")

expenses = [
    {"name": "Housing",             "pct": 0.274},
    {"name": "Groceries",           "pct": 0.141},
    {"name": "Healthcare",          "pct": 0.078},
    {"name": "Transportation",      "pct": 0.079},
    {"name": "Utilities",           "pct": 0.072},
    {"name": "Childcare/activities","pct": 0.061},
    {"name": "Goods & services",    "pct": 0.052},
]

MONTHLY_EXPENSES_NOW = 9567.0
NOW_CPI = 330.293

df_cpi_annual = query("SELECT year, avg_cpi FROM gold.annual_cpi ORDER BY year")
cpi_map = dict(zip(df_cpi_annual["year"], df_cpi_annual["avg_cpi"]))

a_start_cpi = cpi_map.get(a_start, NOW_CPI)
b_start_cpi = cpi_map.get(b_start, NOW_CPI)

exp_col1, exp_col2 = st.columns(2)

with exp_col1:
    st.markdown(f"**Gen A — {a_start}**")
    for e in expenses:
        cost = MONTHLY_EXPENSES_NOW * e["pct"] * (a_start_cpi / NOW_CPI)
        pct  = int((cost / (MONTHLY_EXPENSES_NOW * e["pct"])) * 100)
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:13px;margin-bottom:4px'>"
            f"<span>{e['name']}</span><span>${cost:,.0f}/mo</span></div>"
            f"<div style='background:#e8e8e8;border-radius:3px;height:6px;margin-bottom:8px'>"
            f"<div style='background:#1D9E75;width:{pct}%;height:100%;border-radius:3px'></div></div>",
            unsafe_allow_html=True
        )
    total_a = MONTHLY_EXPENSES_NOW * (a_start_cpi / NOW_CPI)
    st.markdown(f"**Total: ${total_a:,.0f}/mo**")

with exp_col2:
    st.markdown(f"**Gen B — {b_start}**")
    for e in expenses:
        cost = MONTHLY_EXPENSES_NOW * e["pct"] * (b_start_cpi / NOW_CPI)
        pct  = int((cost / (MONTHLY_EXPENSES_NOW * e["pct"])) * 100)
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:13px;margin-bottom:4px'>"
            f"<span>{e['name']}</span><span>${cost:,.0f}/mo</span></div>"
            f"<div style='background:#e8e8e8;border-radius:3px;height:6px;margin-bottom:8px'>"
            f"<div style='background:#185FA5;width:{pct}%;height:100%;border-radius:3px'></div></div>",
            unsafe_allow_html=True
        )
    total_b = MONTHLY_EXPENSES_NOW * (b_start_cpi / NOW_CPI)
    st.markdown(f"**Total: ${total_b:,.0f}/mo**")

# ── summary table ─────────────────────────────────────────
st.subheader("Career comparison")

a_label = f"{a_start}–today" if a_still else f"{a_start}–{a_end}"
b_label = f"{b_start}–today" if b_still else f"{b_start}–{b_end}"

a_end_cpi   = cpi_map.get(a_end_year, NOW_CPI)
b_end_cpi   = cpi_map.get(b_end_year, NOW_CPI)
infla_a     = round(((a_end_cpi / a_start_cpi) - 1) * 100)
infla_b     = round(((b_end_cpi / b_start_cpi) - 1) * 100)
cpi_beats_a = infla_a > (a_wage * (a_end_year - a_start))
cpi_beats_b = infla_b > (b_wage * (b_end_year - b_start))

summary = {
    "Metric": [
        "Career span",
        "Starting salary",
        "Salary at end of career",
        "Monthly surplus at start",
        "Monthly surplus at end",
        "Best month",
        "Worst month",
        "Cumulative inflation",
        "Inflation outpaced wages?",
    ],
    f"Gen A ({a_label})": [
        f"{a_end_year - a_start} years",
        f"${a_income:,.0f}",
        f"${df_a['nominal_salary'].iloc[-1]:,.0f}",
        f"${df_a['monthly_surplus'].iloc[0]:,.0f}/mo",
        f"${df_a['monthly_surplus'].iloc[-1]:,.0f}/mo",
        f"${best_a['monthly_surplus']:,.0f}/mo ({int(best_a['calc_year'])})",
        f"${worst_a['monthly_surplus']:,.0f}/mo ({int(worst_a['calc_year'])})",
        f"+{infla_a}%",
        "Yes — lost ground" if cpi_beats_a else "No — kept pace",
    ],
    f"Gen B ({b_label})": [
        f"{b_end_year - b_start} years",
        f"${b_income:,.0f}",
        f"${df_b['nominal_salary'].iloc[-1]:,.0f}",
        f"${df_b['monthly_surplus'].iloc[0]:,.0f}/mo",
        f"${df_b['monthly_surplus'].iloc[-1]:,.0f}/mo",
        f"${best_b['monthly_surplus']:,.0f}/mo ({int(best_b['calc_year'])})",
        f"${worst_b['monthly_surplus']:,.0f}/mo ({int(worst_b['calc_year'])})",
        f"+{infla_b}%",
        "Yes — lost ground" if cpi_beats_b else "No — kept pace",
    ],
}

st.dataframe(summary, use_container_width=True, hide_index=True)

# ── verdict ───────────────────────────────────────────────
st.subheader("The verdict")

winner = "Gen A" if df_a["monthly_surplus"].iloc[0] > df_b["monthly_surplus"].iloc[0] else "Gen B"
gap    = abs(df_a["monthly_surplus"].iloc[0] - df_b["monthly_surplus"].iloc[0])

verdict_color = "#EAF3DE" if winner == "Gen A" else "#FCEBEB"
verdict_text_color = "#27500A" if winner == "Gen A" else "#791F1F"

st.markdown(
    f"<div style='background:{verdict_color};border-radius:12px;padding:1.25rem;'>"
    f"<p style='color:{verdict_text_color};font-size:15px;font-weight:500;margin-bottom:8px'>"
    f"{winner} started with ${gap:,.0f}/mo more breathing room.</p>"
    f"<p style='color:{verdict_text_color};font-size:13px;line-height:1.65;margin:0'>"
    f"Gen A ({a_start}) started at ${df_a['monthly_surplus'].iloc[0]:,.0f}/mo surplus against "
    f"${total_a:,.0f}/mo in expenses. "
    f"Gen B ({b_start}) started at ${df_b['monthly_surplus'].iloc[0]:,.0f}/mo surplus against "
    f"${total_b:,.0f}/mo in expenses. "
    f"By {b_end_year}, Gen B needed ${b_income * ((b_end_cpi / b_start_cpi)):,.0f} "
    f"just to match their own starting purchasing power after {infla_b}% cumulative inflation. "
    f"The 2021–2023 inflation spike — peaking at 8.98% in 2022 — is visible in the chart "
    f"for anyone whose career overlaps it. Wages did not keep pace."
    f"</p></div>",
    unsafe_allow_html=True
)

# ── footer ────────────────────────────────────────────────
st.divider()
st.caption(
    "Data: FRED API (CPIAUCSL series). Expenses: Morris County NJ baseline "
    "$9,567/mo for married couple with school-age children (apartments.com 2025). "
    "Wage growth compounded annually from starting salary. Not financial advice."
)