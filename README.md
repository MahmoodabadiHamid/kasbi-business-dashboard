# Kasbi · Finance decisions

A runnable, read-only executive dashboard for the financial unit economics of Kasbi's managed, dedicated driver service for pharmaceutical companies. It answers the 20 decision questions where available and identifies evidence gaps where a source cannot support an honest answer.

## Start in five minutes

Python 3.11+ and Microsoft ODBC Driver 18 for SQL Server are recommended.

Copy `.env.example` to `.env` and set the SQL Server details. Leave `SQL_USERNAME` and `SQL_PASSWORD` blank to use Windows Integrated Security; fill both fields only if you use SQL username/password auth.

```bash
SQL_SERVER=your-sql-server-host
SQL_DATABASE=TooranFramework
SQL_USERNAME=
SQL_PASSWORD=
SQL_DRIVER=ODBC Driver 18 for SQL Server
SQL_ENCRYPT=yes
SQL_TRUST_SERVER_CERTIFICATE=no
```

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

If a Windows launcher points at an old folder, use the module form instead:

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local address printed by Streamlit. The default view starts at **1405.01.12 (Shamsi)** with no end-date limit, all geographies, and all organizations. Dates use the Shamsi (Jalali) calendar in year.month.day format. Enter start/end dates in the sidebar; Persian and Arabic digits and dot, slash or dash separators are accepted. Blank bounds are unrestricted, an end date is inclusive, and a start date alone includes all later trips. Invalid or reversed dates show a validation message. Use the sidebar to filter the data or choose **Clear all filters** to restore the full history. The app reads trips and destinations directly from SQL Server using the two parameterized queries under `sql/`; it does not create CSV extracts or read uploaded files. Monetary values are displayed as Iranian toman (1 toman = 10 IRR). Metrics, tables, chart axes and tooltips abbreviate billions as B and millions as M (for example, 4 B and 6 M), using up to two decimal places; smaller amounts are rounded to whole toman with thousands separators. Displayed amounts convert stored rial amounts by dividing by 10; calculations and reconciliation continue to use the original rial values. CSV downloads contain numeric toman amounts without display rounding, with `_toman` suffixes on monetary column names and a `_toman.csv` filename. Exported timestamps use Shamsi dates with `_shamsi` column suffixes and preserve the original time of day. Source timestamps and date filtering remain Gregorian internally. Dates represent the database's local timestamps; agree on timezone and accounting cutoff. The database and schema names match the supplied sample and earlier conversation: `[TooranFramework].[tooranDb]`. Adapt them in both SQL files if your deployment differs. Keep `.env` private.

## Visual language

The dashboard uses a shared palette in `finance/theme.py`: electric blue (`#00A3FF`) for passenger fare, neon green (`#00E6A0`) for positive contribution, neon pink (`#FF3B8D`) for costs, and neon red (`#FF1744`) for losses. Translucent fills use the same hues. Charts and metric-card borders share these meanings; negative contribution bars use neon red, while cost cards use the matching pink accent. Numbers, labels and loss markers communicate the same information alongside color. White cards, a platinum background, consistent chart styling, visible keyboard focus and responsive card rows keep the view readable at different widths. Main and secondary text colors were checked against white for contrast; this does not constitute a full accessibility audit.

## Calculation baseline

The authoritative daily SQL is [sql/daily_totals.sql](sql/daily_totals.sql). Its formulas govern trip, daily, customer, segment, chart, pricing and export calculations:

| Field | Formula in source IRR |
| --- | --- |
| Passenger fare | `CAST(TripCost AS DECIMAL(18,2)) * 0.922` |
| Driver payout | `CAST(TripDriverCost AS DECIMAL(18,2))` |
| Contribution | `SUM(PassengerFare) - SUM(DriverPayout)` |
| MarginPercent | `(SUM(PassengerFare) - SUM(DriverPayout)) * 100 / NULLIF(SUM(PassengerFare),0)` |
| Daily displayed passenger fare | `FLOOR(SUM(PassengerFare)/10)` toman |
| Daily displayed driver payout | `FLOOR(SUM(DriverPayout)/10)` toman |
| Target-margin source TripCost | `DriverPayout / (0.922 * (1-target_margin))` |

Neither StopTimeCost nor StopTimeDriverCost is added to the financial baseline. Both remain visible as recorded diagnostics. No extra insurance expense, fare deduction or markup reversal is inferred.

Input amounts are rounded to two rial decimals before multiplication, using SQL-compatible half-away-from-zero rounding. Decimal-backed sums avoid ordinary floating-point accumulation errors; numeric chart boundaries use floats. The daily baseline table floors toman amounts only after summation and shows margin rounded to two decimals from unrounded IRR totals. Trip-review CSV values retain numeric toman precision and use `passenger_fare_toman` and `driver_payout_toman`. Compact KPI displays and charts retain their abbreviated presentation and are not the formatted SQL output.

Business scope excludes organization **سرویس تست رایگان** by trimmed organization name, in all SQL retrieval/report scripts and Python preparation. Other organizations, including missing organization references, remain included. Within this scope, the baseline retains all source rows. It does not filter by status, completed end time, amount sign, missing monetary components or duplicate trip IDs. SQL-style NULL amounts are summed independently; a group with no known values returns unknown rather than zero. IDs and missing dates remain data-quality diagnostics. Duplicate IDs are retained in baseline totals but excluded from ambiguous trip-to-destination comparisons. A missing start date forms an unknown-date group when no date filter is selected; dated charts cannot plot that group. Invalid or over-72-hour durations affect hourly metrics only.

## Database scope and review

The live loader executes trips.sql and destinations.sql separately with optional date bounds (inclusive start, exclusive end). It currently loads all history. Sidebar filters are then applied in Python. The default start date remains 1405.01.12; **Clear all filters** is required to compare the dashboard with the unfiltered daily SQL. Sidebar end dates are inclusive.

No hard-coded dates are excluded from charts. The percentage chart requires positive daily passenger fare and known nonnegative payout for its band geometry; omitted percentage-chart days remain in baseline totals and the daily table. Hourly and pricing scenarios are supplementary analyses, not additional baseline filters. Pricing scenarios and loss-trip rates use rows with both fare and payout known; this does not change independent baseline sums.

Destination fields are source-charge diagnostics, not an approved allocation of PassengerFare or DriverPayout. Component sums and comparisons with raw TripCost are labeled source comparisons; no stop-inclusive trip total or destination contribution is invented. Missing values and incomplete benchmark coverage remain visible. Route/Snapp comparisons use only complete positive benchmark subsets and do not establish business-wide pricing compliance.

The [DBA review package](sql/DBA_QUERY_REVIEW.md) contains all seven current SQL files, their names, purposes and calculation rules. retrieval_queries_review.sql is the SSMS version of the live retrieval queries. Daily and single-date diagnostic scripts use the same passenger fare / payout definitions. No SQL Server data was changed.

The dashboard caches prepared history for five minutes. Refresh data reloads the source; the revised calculation policy has a new cache key. Organization and city labels come from lookup tables. SQL source timestamps remain Gregorian; dashboard dates and exports use Shamsi presentation. Stored IRR is divided by 10 for toman.

The supplied SnapPrice is not validated as snapp_plus_final. Pricing scenarios hold driver payout fixed and exclude additional costs and demand response. Contribution is not net profit or cash collection.

## Review & verification

Only the selected tab builds its charts and tables. The Data trust CSV is generated when the download is clicked, using the selected snapshot and filters. Destination totals and grouped metrics use vectorized reductions, preserving missing amounts, coverage checks and the valid-hour subset used by hourly ratios.

For repeatable performance checks without querying SQL Server:

```bash
python scripts/benchmark_dashboard.py --trips 20000 --app
```

The benchmark generates 20,000 trips and 60,000 destinations and times preparation, daily grouping, initial app rendering and a cached filter change. It also reports database-load call counts; the SQL result is mocked, so these timings exclude network and database latency. On the development machine, preparation dropped from about 7.9 s to 0.08 s, initial rendering from 14.7 s to 4.3 s, and the filter change from 11.2 s to 0.6 s. Exact times depend on hardware, data size and import warm-up.

```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py finance
```

The tests cover double counting, weighted margins, reconciliation, missing destinations and competitor price completeness. Finance should reconcile the loaded database period to final invoices and driver settlements, confirm refund and tax treatment, and review **Data trust** row-level reconciliation and coverage before using it as an official financial statement.
