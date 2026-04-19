import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from databricks import sql

st.set_page_config(
    page_title="What Did Money Used to Mean?",
    page_icon="$",
    layout="wide"
)

# ── constants ─────────────────────────────────────────────
MONTHLY_EXPENSES_NOW = 9567.0
NOW_CPI              = 330.293
DAYCARE_COST_NOW     = 2200.0   # per child per month
AFTERCARE_COST_NOW   = 600.0    # per child per month
RENT_BASELINE_NOW    = 2781.0   # Morris County avg rent
MORTGAGE_BASELINE_NOW= 3150.0   # Morris County avg mortgage

EXPENSES_BASE = [
    {"name": "Housing",              "pct": 0.274},
    {"name": "Groceries",            "pct": 0.141},
    {"name": "Healthcare",           "pct": 0.078},
    {"name": "Transportation",       "pct": 0.079},
    {"name": "Utilities",            "pct": 0.072},
    {"name": "Goods & services",     "pct": 0.052},
]

# ── databricks connection ─────────────────────────────────
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

# ── load CPI map once ─────────────────────────────────────
@st.cache_data(ttl=3600)
def load_cpi_map():
    df = query("SELECT year, avg_cpi FROM gold.annual_cpi ORDER BY year")
    return dict(zip(df["year"], df["avg_cpi"]))

cpi_map = load_cpi_map()

# ── expense calculator ────────────────────────────────────
def calc_monthly_expenses(start_year, owns_home, kids_daycare, kids_aftercare):
    cpi_ratio = cpi_map.get(start_year, NOW_CPI) / NOW_CPI
    # base expenses scaled by CPI
    base = MONTHLY_EXPENSES_NOW * cpi_ratio
    # replace housing component with own/rent specific value
    housing_now = MORTGAGE_BASELINE_NOW if owns_home else RENT_BASELINE_NOW
    housing_then = housing_now * cpi_ratio
    base = (base - MONTHLY_EXPENSES_NOW * 0.274) + housing_then
    # add childcare
    daycare_then   = DAYCARE_COST_NOW   * kids_daycare   * cpi_ratio
    aftercare_then = AFTERCARE_COST_NOW * kids_aftercare * cpi_ratio
    return base + daycare_then + aftercare_then

def calc_tax_rate(combined_income, married):
    # simplified effective federal + NJ rate
    if married:
        if combined_income < 50000:   return 0.12
        elif combined_income < 90000: return 0.17
        elif combined_income < 130000:return 0.21
        elif combined_income < 200000:return 0.25
        else:                         return 0.30
    else:
        if combined_income < 40000:   return 0.15
        elif combined_income < 80000: return 0.20
        elif combined_income < 120000:return 0.24
        else:                         return 0.29

def build_profile(prefix):
    st.sidebar.subheader(f"Generation {prefix}")

    start = st.sidebar.slider(
        "Started working", 1950, 2020, 
        1950 if prefix == "A" else 2000,
        key=f"{prefix}_start"
    )
    still = st.sidebar.checkbox(
        "Still working today", value=True, key=f"{prefix}_still"
    )
    end = st.sidebar.slider(
        "Stopped working", 1951, 2025,
        1985 if prefix == "A" else 2025,
        disabled=still, key=f"{prefix}_end"
    )

    st.sidebar.markdown("**Income**")
    income1 = st.sidebar.number_input(
        "Primary income ($)", value=3500 if prefix == "A" else 45000,
        step=500, key=f"{prefix}_inc1"
    )
    dual = st.sidebar.checkbox("Add second income?", key=f"{prefix}_dual")
    income2 = 0
    if dual:
        income2 = st.sidebar.number_input(
            "Second income ($)", value=0, step=500, key=f"{prefix}_inc2"
        )
    combined = income1 + income2
    if dual:
        st.sidebar.caption(f"Combined: ${combined:,.0f}/yr")

    wage = st.sidebar.select_slider(
        "Annual wage growth (primary)",
        options=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0],
        value=3.0,
        format_func=lambda x: f"{x:.1f}%",
        key=f"{prefix}_wage"
    )

    st.sidebar.markdown("**Household**")
    married   = st.sidebar.selectbox(
        "Marital status", ["Married", "Single"],
        key=f"{prefix}_married"
    ) == "Married"
    owns_home = st.sidebar.selectbox(
        "Housing", ["Own (mortgage)", "Rent"],
        key=f"{prefix}_own"
    ) == "Own (mortgage)"

    st.sidebar.markdown("**Kids**")
    kids_daycare   = st.sidebar.number_input(
        "Kids in daycare",   min_value=0, max_value=5, value=0, key=f"{prefix}_daycare"
    )
    kids_aftercare = st.sidebar.number_input(
        "Kids in aftercare", min_value=0, max_value=5, value=0, key=f"{prefix}_aftercare"
    )
    kids_neither   = st.sidebar.number_input(
        "Kids (no childcare)", min_value=0, max_value=5, value=0, key=f"{prefix}_neither"
    )

    return {
        "start": start, "end": end, "still": still,
        "income1": income1, "income2": income2,
        "combined": combined, "dual": dual,
        "wage": wage, "married": married,
        "owns_home": owns_home,
        "kids_daycare": kids_daycare,
        "kids_aftercare": kids_aftercare,
        "kids_neither": kids_neither,
        "total_kids": kids_daycare + kids_aftercare + kids_neither,
    }

# ── header ────────────────────────────────────────────────
st.title("What did money used to mean?")
st.caption(
    "A generational purchasing power calculator. "
    "Real CPI data from FRED. Morris County, NJ baseline expenses."
)

# ── sidebar ───────────────────────────────────────────────
a = build_profile("A")

st.sidebar.divider()

copy = st.sidebar.button("Copy Gen A settings to Gen B")

if copy:
    for key in ["start","still","end","inc1","dual","inc2",
                "wage","married","own","daycare","aftercare","neither"]:
        if f"A_{key}" in st.session_state:
            st.session_state[f"B_{key}"] = st.session_state[f"A_{key}"]
    st.rerun()

b = build_profile("B")

# ── derived values ────────────────────────────────────────
a_end_year = 2025 if a["still"] else a["end"]
b_end_year = 2025 if b["still"] else b["end"]

a_tax = calc_tax_rate(a["combined"], a["married"])
b_tax = calc_tax_rate(b["combined"], b["married"])

a_net_income = a["combined"] * (1 - a_tax)
b_net_income = b["combined"] * (1 - b_tax)

a_expenses_start = calc_monthly_expenses(
    a["start"], a["owns_home"], a["kids_daycare"], a["kids_aftercare"]
)
b_expenses_start = calc_monthly_expenses(
    b["start"], b["owns_home"], b["kids_daycare"], b["kids_aftercare"]
)

# ── query gold tables ─────────────────────────────────────
df_a = query(f"""
    SELECT calc_year, monthly_surplus, nominal_salary, real_expenses
    FROM gold.generational_comparison
    WHERE start_year     = {a["start"]}
    AND wage_growth_pct  = {a["wage"]}
    AND calc_year       <= {a_end_year}
    ORDER BY calc_year
""")

df_b = query(f"""
    SELECT calc_year, monthly_surplus, nominal_salary, real_expenses
    FROM gold.generational_comparison
    WHERE start_year     = {b["start"]}
    AND wage_growth_pct  = {b["wage"]}
    AND calc_year       <= {b_end_year}
    ORDER BY calc_year
""")

# scale by actual combined net income vs base $50k gross
df_a["monthly_surplus"] = df_a["monthly_surplus"] * (a_net_income / 50000)
df_a["nominal_salary"]  = df_a["nominal_salary"]  * (a["combined"] / 50000)
df_b["monthly_surplus"] = df_b["monthly_surplus"] * (b_net_income / 50000)
df_b["nominal_salary"]  = df_b["nominal_salary"]  * (b["combined"] / 50000)

# apply childcare and housing adjustments
cpi_ratio_a = cpi_map.get(a["start"], NOW_CPI) / NOW_CPI
cpi_ratio_b = cpi_map.get(b["start"], NOW_CPI) / NOW_CPI

childcare_a = (
    DAYCARE_COST_NOW   * a["kids_daycare"]   +
    AFTERCARE_COST_NOW * a["kids_aftercare"]
) * cpi_ratio_a

childcare_b = (
    DAYCARE_COST_NOW   * b["kids_daycare"]   +
    AFTERCARE_COST_NOW * b["kids_aftercare"]
) * cpi_ratio_b

df_a["monthly_surplus"] = df_a["monthly_surplus"] - childcare_a
df_b["monthly_surplus"] = df_b["monthly_surplus"] - childcare_b

# ── summary metrics ───────────────────────────────────────
st.markdown("### Household summary")
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Gen A gross income",   f"${a['combined']:,.0f}/yr")
with col2:
    st.metric("Gen A take-home",
        f"${a_net_income:,.0f}/yr",
        delta=f"{a_tax*100:.0f}% tax"
    )
with col3:
    st.metric("Gen A starting surplus",
        f"${df_a['monthly_surplus'].iloc[0]:,.0f}/mo")
with col4:
    st.metric("Gen B gross income",   f"${b['combined']:,.0f}/yr")
with col5:
    st.metric("Gen B take-home",
        f"${b_net_income:,.0f}/yr",
        delta=f"{b_tax*100:.0f}% tax"
    )
with col6:
    st.metric("Gen B starting surplus",
        f"${df_b['monthly_surplus'].iloc[0]:,.0f}/mo")

# ── main chart ────────────────────────────────────────────
st.subheader("Real monthly surplus or deficit — full career arc")

worst_a = df_a.loc[df_a["monthly_surplus"].idxmin()]
best_a  = df_a.loc[df_a["monthly_surplus"].idxmax()]
worst_b = df_b.loc[df_b["monthly_surplus"].idxmin()]
best_b  = df_b.loc[df_b["monthly_surplus"].idxmax()]

a_label = f"Gen A ({a['start']}, {a['wage']:.1f}% raises)"
b_label = f"Gen B ({b['start']}, {b['wage']:.1f}% raises)"

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df_a["calc_year"], y=df_a["monthly_surplus"],
    name=a_label,
    line=dict(color="#1D9E75", width=2),
    fill="tozeroy", fillcolor="rgba(29,158,117,0.08)",
    hovertemplate="<b>%{x}</b><br>Gen A: $%{y:,.0f}/mo<extra></extra>"
))

fig.add_trace(go.Scatter(
    x=df_b["calc_year"], y=df_b["monthly_surplus"],
    name=b_label,
    line=dict(color="#185FA5", width=2),
    fill="tozeroy", fillcolor="rgba(24,95,165,0.08)",
    hovertemplate="<b>%{x}</b><br>Gen B: $%{y:,.0f}/mo<extra></extra>"
))

fig.add_hline(
    y=0, line_dash="dash",
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
        tickprefix="$", tickformat=",.0f",
        gridcolor="rgba(128,128,128,0.1)"
    ),
    xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# ── expense breakdown ─────────────────────────────────────
st.subheader("Monthly expenses at career start")

exp_col1, exp_col2 = st.columns(2)

def render_expenses(col, profile, expenses_total, cpi_ratio, label):
    with col:
        st.markdown(f"**{label}**")
        housing_now = MORTGAGE_BASELINE_NOW if profile["owns_home"] else RENT_BASELINE_NOW
        for e in EXPENSES_BASE:
            if e["name"] == "Housing":
                cost = housing_now * cpi_ratio
            else:
                cost = MONTHLY_EXPENSES_NOW * e["pct"] * cpi_ratio
            pct = min(int((cost / (MONTHLY_EXPENSES_NOW * e["pct"])) * 100), 100)
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:13px;margin-bottom:4px'>"
                f"<span>{e['name']}</span><span>${cost:,.0f}/mo</span></div>"
                f"<div style='background:#e8e8e8;border-radius:3px;height:6px;"
                f"margin-bottom:8px'><div style='background:#1D9E75;width:{pct}%;"
                f"height:100%;border-radius:3px'></div></div>",
                unsafe_allow_html=True
            )
        # childcare rows
        if profile["kids_daycare"] > 0:
            cost = DAYCARE_COST_NOW * profile["kids_daycare"] * cpi_ratio
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:13px;margin-bottom:4px'>"
                f"<span>Daycare ({profile['kids_daycare']} kid{'s' if profile['kids_daycare']>1 else ''})"
                f"</span><span>${cost:,.0f}/mo</span></div>"
                f"<div style='background:#e8e8e8;border-radius:3px;height:6px;"
                f"margin-bottom:8px'><div style='background:#E24B4A;width:100%;"
                f"height:100%;border-radius:3px'></div></div>",
                unsafe_allow_html=True
            )
        if profile["kids_aftercare"] > 0:
            cost = AFTERCARE_COST_NOW * profile["kids_aftercare"] * cpi_ratio
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:13px;margin-bottom:4px'>"
                f"<span>Aftercare ({profile['kids_aftercare']} kid{'s' if profile['kids_aftercare']>1 else ''})"
                f"</span><span>${cost:,.0f}/mo</span></div>"
                f"<div style='background:#e8e8e8;border-radius:3px;height:6px;"
                f"margin-bottom:8px'><div style='background:#EF9F27;width:80%;"
                f"height:100%;border-radius:3px'></div></div>",
                unsafe_allow_html=True
            )
        st.markdown(f"**Total: ${expenses_total:,.0f}/mo**")

render_expenses(exp_col1, a, a_expenses_start, cpi_ratio_a,
    f"Gen A — {a['start']} ({'Married' if a['married'] else 'Single'}, "
    f"{'owns' if a['owns_home'] else 'rents'}, {a['total_kids']} kid{'s' if a['total_kids']!=1 else ''})"
)
render_expenses(exp_col2, b, b_expenses_start, cpi_ratio_b,
    f"Gen B — {b['start']} ({'Married' if b['married'] else 'Single'}, "
    f"{'owns' if b['owns_home'] else 'rents'}, {b['total_kids']} kid{'s' if b['total_kids']!=1 else ''})"
)

# ── summary table ─────────────────────────────────────────
st.subheader("Career comparison")

a_end_cpi   = cpi_map.get(a_end_year, NOW_CPI)
b_end_cpi   = cpi_map.get(b_end_year, NOW_CPI)
a_start_cpi = cpi_map.get(a["start"], NOW_CPI)
b_start_cpi = cpi_map.get(b["start"], NOW_CPI)
infla_a     = round(((a_end_cpi / a_start_cpi) - 1) * 100)
infla_b     = round(((b_end_cpi / b_start_cpi) - 1) * 100)
cpi_beats_a = infla_a > (a["wage"] * (a_end_year - a["start"]))
cpi_beats_b = infla_b > (b["wage"] * (b_end_year - b["start"]))

summary = {
    "Metric": [
        "Career span",
        "Household type",
        "Combined gross income",
        "Effective tax rate",
        "Annual take-home",
        "Monthly expenses at start",
        "Monthly surplus at start",
        "Monthly surplus at end",
        "Best month",
        "Worst month",
        "Salary at end of career",
        "Cumulative inflation",
        "Inflation outpaced wages?",
    ],
    f"Gen A ({a['start']}–{a_end_year})": [
        f"{a_end_year - a['start']} years",
        f"{'Married' if a['married'] else 'Single'}, "
        f"{'owns' if a['owns_home'] else 'rents'}, "
        f"{a['total_kids']} kid{'s' if a['total_kids']!=1 else ''}",
        f"${a['combined']:,.0f}",
        f"{a_tax*100:.0f}%",
        f"${a_net_income:,.0f}",
        f"${a_expenses_start:,.0f}/mo",
        f"${df_a['monthly_surplus'].iloc[0]:,.0f}/mo",
        f"${df_a['monthly_surplus'].iloc[-1]:,.0f}/mo",
        f"${best_a['monthly_surplus']:,.0f}/mo ({int(best_a['calc_year'])})",
        f"${worst_a['monthly_surplus']:,.0f}/mo ({int(worst_a['calc_year'])})",
        f"${df_a['nominal_salary'].iloc[-1]:,.0f}",
        f"+{infla_a}%",
        "Yes — lost ground" if cpi_beats_a else "No — kept pace",
    ],
    f"Gen B ({b['start']}–{b_end_year})": [
        f"{b_end_year - b['start']} years",
        f"{'Married' if b['married'] else 'Single'}, "
        f"{'owns' if b['owns_home'] else 'rents'}, "
        f"{b['total_kids']} kid{'s' if b['total_kids']!=1 else ''}",
        f"${b['combined']:,.0f}",
        f"{b_tax*100:.0f}%",
        f"${b_net_income:,.0f}",
        f"${b_expenses_start:,.0f}/mo",
        f"${df_b['monthly_surplus'].iloc[0]:,.0f}/mo",
        f"${df_b['monthly_surplus'].iloc[-1]:,.0f}/mo",
        f"${best_b['monthly_surplus']:,.0f}/mo ({int(best_b['calc_year'])})",
        f"${worst_b['monthly_surplus']:,.0f}/mo ({int(worst_b['calc_year'])})",
        f"${df_b['nominal_salary'].iloc[-1]:,.0f}",
        f"+{infla_b}%",
        "Yes — lost ground" if cpi_beats_b else "No — kept pace",
    ],
}

st.dataframe(summary, use_container_width=True, hide_index=True)

# ── verdict ───────────────────────────────────────────────
st.subheader("The verdict")

gap    = abs(df_a["monthly_surplus"].iloc[0] - df_b["monthly_surplus"].iloc[0])
winner = "Gen A" if df_a["monthly_surplus"].iloc[0] > df_b["monthly_surplus"].iloc[0] else "Gen B"
verdict_color      = "#EAF3DE" if winner == "Gen A" else "#FCEBEB"
verdict_text_color = "#27500A" if winner == "Gen A" else "#791F1F"

st.markdown(
    f"<div style='background:{verdict_color};border-radius:12px;padding:1.25rem;'>"
    f"<p style='color:{verdict_text_color};font-size:15px;font-weight:500;margin-bottom:8px'>"
    f"{winner} started with ${gap:,.0f}/mo more breathing room.</p>"
    f"<p style='color:{verdict_text_color};font-size:13px;line-height:1.65;margin:0'>"
    f"Gen A ({a['start']}, {'married' if a['married'] else 'single'}, "
    f"{'owns' if a['owns_home'] else 'rents'}): "
    f"${a['combined']:,.0f} gross → ${a_net_income:,.0f} take-home after {a_tax*100:.0f}% taxes "
    f"against ${a_expenses_start:,.0f}/mo in expenses — "
    f"leaving ${df_a['monthly_surplus'].iloc[0]:,.0f}/mo. "
    f"Gen B ({b['start']}, {'married' if b['married'] else 'single'}, "
    f"{'owns' if b['owns_home'] else 'rents'}): "
    f"${b['combined']:,.0f} gross → ${b_net_income:,.0f} take-home after {b_tax*100:.0f}% taxes "
    f"against ${b_expenses_start:,.0f}/mo in expenses — "
    f"leaving ${df_b['monthly_surplus'].iloc[0]:,.0f}/mo. "
    f"By {b_end_year}, cumulative inflation of {infla_b}% meant Gen B needed "
    f"${b['combined'] * (b_end_cpi / b_start_cpi):,.0f} just to match "
    f"their own starting purchasing power."
    f"</p></div>",
    unsafe_allow_html=True
)

# ── inflation context chart ───────────────────────────────
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
    yaxis=dict(ticksuffix="%", gridcolor="rgba(128,128,128,0.1)"),
    xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
    hovermode="x unified"
)

st.plotly_chart(fig2, use_container_width=True)
st.caption("Green = under 3% | Orange = 3–5% | Red = over 5%. Source: BLS CPI-U via FRED.")

# ── footer ────────────────────────────────────────────────
st.divider()
st.caption(
    "Data: FRED API (CPIAUCSL series). Expenses: Morris County NJ baseline "
    "$9,567/mo for married couple with school-age children (apartments.com 2025). "
    "Daycare cost: $2,200/mo per child (NJ average 2025). "
    "Aftercare: $600/mo per child. Tax rates are simplified estimates. "
    "Wage growth compounded annually from starting salary. Not financial advice."
)