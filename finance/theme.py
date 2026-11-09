"""Shared visual tokens for the dashboard and financial charts."""

TEXT = "#18232D"
MUTED = "#586574"
REVENUE = "#00A3FF"
PROFIT = "#00E6A0"
COST = "#FF3B8D"
LOSS = "#FF1744"
LOSS_FILL = "rgba(255,23,68,0.58)"
GRID = "#E4E8EC"
PROFIT_FILL = "rgba(0,230,160,0.42)"
COST_FILL = "rgba(255,59,141,0.28)"
NEUTRAL_FILL = "rgba(0,163,255,0.06)"
FONT = "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

PLOT_LAYOUT = dict(
    template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT, color=TEXT, size=12),
    title=dict(font=dict(size=15, color=TEXT), x=0, xanchor="left"),
    margin=dict(l=18, r=18, t=48, b=72), height=365,
    hovermode="closest",
    hoverlabel=dict(bgcolor=TEXT, bordercolor=TEXT, font=dict(family=FONT, size=13, color="#FFFFFF"), namelength=-1),
    legend=dict(orientation="h", y=-.24, x=0, font=dict(size=12, color=MUTED)),
    colorway=[REVENUE, COST, PROFIT],
)

_CSS_COLORS = {
    "text": TEXT, "muted": MUTED, "passenger_fare": REVENUE, "profit": PROFIT, "cost": COST,
    "background": "#F5F6F8", "surface": "#FFFFFF", "border": "#DCE2E7",
    "profit-border": "#A8EFD9", "cost-border": "#FFC2DB", "passenger_fare-border": "#AADFFF",
    "focus": "#4C6688",
}
DASHBOARD_CSS = "<style>:root{" + ";".join(f"--{key}:{value}" for key, value in _CSS_COLORS.items()) + "}" + """
 .stApp {background:var(--background); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
 .block-container {max-width:1600px; padding:2.25rem clamp(1.25rem,3vw,3rem) 3rem}
 [data-testid="stSidebar"] {background:#EFF1F4; border-right:1px solid var(--border)}
 [data-testid="stMetric"], .money-metric {box-sizing:border-box; background:var(--surface); border:1px solid var(--border); border-top:2px solid #B9C3CD; border-radius:14px; padding:18px 20px; min-height:128px; box-shadow:0 2px 8px #18232D04; display:flex; flex-direction:column; justify-content:space-between}
 .metric--profit, [class*="st-key-kpi-profit-"] [data-testid="stMetric"] {border-color:var(--profit-border); border-top-color:var(--profit)}
 .metric--cost, [class*="st-key-kpi-cost-"] [data-testid="stMetric"] {border-color:var(--cost-border); border-top-color:var(--cost)}
 .metric--passenger_fare, [class*="st-key-kpi-passenger_fare-"] [data-testid="stMetric"] {border-color:var(--passenger_fare-border); border-top-color:var(--passenger_fare)}
 [data-testid="stMetricLabel"], .money-metric-label {font-size:14px; line-height:1.45; font-weight:500; color:var(--muted)}
 [data-testid="stMetricLabel"] p {white-space:normal; overflow:visible; text-overflow:clip}
 [data-testid="stMetricValue"], .money-metric-amount {font-size:clamp(22px,2vw,30px); color:var(--text); font-weight:600; letter-spacing:-.035em; font-variant-numeric:tabular-nums}
 .money-metric-label {min-height:40px; margin-bottom:8px}
 .money-metric-value {display:flex; align-items:baseline; flex-wrap:wrap; gap:4px 8px; min-height:36px; line-height:1.2}
 .money-metric-amount {white-space:nowrap}
 .money-metric-unit {font-size:12px; font-weight:500; color:var(--muted); white-space:nowrap; letter-spacing:0}
 .hero {background:var(--surface); border:1px solid var(--border); border-radius:18px; padding:28px 32px; margin-bottom:20px}
 .hero h1 {color:var(--text); margin:0 0 10px; font-size:clamp(25px,3vw,34px); line-height:1.2; font-weight:600; letter-spacing:-.04em}
 .hero p {color:var(--muted); margin:0; font-size:14px; line-height:1.6}
 .semantic-legend {display:flex; flex-wrap:wrap; gap:8px 24px; margin-top:18px; font-size:12px; color:var(--muted)}
 .semantic-legend span {display:inline-flex; align-items:center; gap:7px}
 .semantic-legend i {width:8px; height:8px; border-radius:50%; display:inline-block; background:var(--passenger_fare)}
 .semantic-legend .cost i {background:var(--cost)}
 .semantic-legend .profit i {background:var(--profit)}
 .callout {background:#F0F4F3; border:1px solid #D4E1DC; border-left:3px solid var(--profit); border-radius:10px; padding:16px 20px; margin:24px 0 8px; font-size:13px; line-height:1.7; color:var(--muted)}
 .warn {background:#F8F3F1; border:1px solid #E6D8D3; border-left:3px solid var(--cost); border-radius:10px; padding:14px 18px; margin:12px 0 20px; font-size:14px; line-height:1.6}
 .subtle, [data-testid="stCaptionContainer"] {color:var(--muted); font-size:13px; line-height:1.65}
 h2, h3 {color:var(--text); font-weight:600; letter-spacing:-.025em}
 [data-testid="stTabs"] [role="tablist"] {gap:24px; border-bottom:1px solid var(--border)}
 [data-testid="stTabs"] [role="tab"] {font-weight:500; font-size:14px; padding:10px 0; min-height:44px}
 [data-testid="stTabs"] [role="tab"][aria-selected="true"] {color:var(--text); font-weight:600}
 [data-baseweb="tab-highlight"] {background:var(--passenger_fare)}
 [data-testid="stPlotlyChart"] {background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:8px; overflow:hidden}
 [data-testid="stDataFrame"], [data-testid="stExpander"] {border-radius:12px}
 [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {min-height:44px; border-radius:9px; font-weight:500}
 button:focus-visible, input:focus-visible, [role="tab"]:focus-visible {outline:2px solid var(--focus); outline-offset:3px}
 [data-testid="stHorizontalBlock"]:has(.money-metric) {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); grid-auto-rows:minmax(128px,auto); height:auto !important; gap:16px !important}
 [data-testid="stHorizontalBlock"]:has(.money-metric):has(> [data-testid="stColumn"]:nth-child(3):last-child) {grid-template-columns:repeat(3,minmax(0,1fr))}
 [data-testid="stHorizontalBlock"]:has(.money-metric) > [data-testid="stColumn"] {width:100%; min-width:0; min-height:128px; height:auto !important}
 [data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"]) {flex-wrap:wrap; gap:16px !important}
 [data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"]) > [data-testid="stColumn"] {flex:1 1 420px; min-width:0}
 @media(max-width:1450px) {
   [data-testid="stHorizontalBlock"]:has(.money-metric),
   [data-testid="stHorizontalBlock"]:has(.money-metric):has(> [data-testid="stColumn"]:nth-child(3):last-child) {grid-template-columns:repeat(2,minmax(0,1fr))}
   [data-testid="stHorizontalBlock"]:has(.money-metric) > [data-testid="stColumn"]:nth-child(3):last-child {grid-column:1 / -1}
 }
 @media(max-width:900px) {
   .block-container {padding-top:1.5rem}
   .hero {padding:22px}
 }
 @media(max-width:600px) {
   [data-testid="stHorizontalBlock"]:has(.money-metric),
   [data-testid="stHorizontalBlock"]:has(.money-metric):has(> [data-testid="stColumn"]:nth-child(3):last-child) {grid-template-columns:minmax(0,1fr)}
 }
 @media(prefers-reduced-motion:reduce) {*, *::before, *::after {scroll-behavior:auto !important; transition:none !important; animation:none !important}}
</style>
"""
