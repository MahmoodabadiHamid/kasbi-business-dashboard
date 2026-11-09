# DBA query review

Revision: 2026-11-08. The supplied DailyTotals query is authoritative. All seven current SQL files are reproduced below. Run each script separately.

Business scope excludes organization **سرویس تست رایگان** in all queries. SQL uses NOT EXISTS against Organizations, preserving missing organization references. Names are trimmed; no fuzzy name matching is applied. Python also enforces this exclusion for non-SQL inputs and drops the excluded trips' destinations from analysis.

## Calculation contract

- PassengerFare = CAST(TripCost AS DECIMAL(18,2)) * 0.922.
- DriverPayout = CAST(TripDriverCost AS DECIMAL(18,2)), with no stop payout added.
- Contribution = SUM(PassengerFare) - SUM(DriverPayout). Each sum ignores NULL independently.
- MarginPercent = contribution * 100 / NULLIF(SUM(PassengerFare),0), rounded to DECIMAL(10,2) for the daily report.
- Daily passenger fare and payout displays use FORMAT(FLOOR(daily sum in IRR / 10),'#,0'). Flooring is after summation, not per trip. Margin uses unrounded IRR totals.
- Neither stop field enters these totals. There is no additional inferred insurance accounting or destination financial allocation.
- No status, end-time, positive-fare, nonnegative-payout, missing-ID or duplicate-ID exclusion is added. Missing source amounts remain unknown; all-null groups remain NULL.
- Live retrieval has optional start-date bounds; diagnostics explicitly declare their date scope. The unfiltered daily baseline includes the NULL start-date group. Dashboard default sidebar date filters must be cleared for an all-history comparison.
- Hourly metrics, percentage chart geometry and positive-benchmark comparisons have their own visible scope; they do not remove rows from baseline totals. No historical dates are excluded by policy.
- Source trip/destination amount comparisons are diagnostic only. The daily baseline does not define a destination fare/payout allocation, or say either trip amount needs another stop component added.

## Files

| Filename | Purpose |
| --- | --- |
| `daily_totals.sql` | Authoritative all-history daily baseline |
| `trips.sql` | Live trip retrieval |
| `destinations.sql` | Live destination source retrieval |
| `retrieval_queries_review.sql` | SSMS copies of the two live queries |
| `daily_contribution_july_2026.sql` | Same daily baseline limited to July 2026 |
| `check_costs_1405_05_09.sql` | Daily, trip and organization/driver investigation for 2026-07-31 |
| `check_destination_contribution_1405_05_09.sql` | Trip baseline plus raw destination fields for 2026-07-31 |

## Verification and limits

Regression tests cover stop-field independence, duplicate/negative/zero rows, missing end dates, independent NULL sums, two-decimal source casts, aggregate-before-floor display, zero-denominator margin and dashboard filters/exports. SQL Server execution and current schema constraints require DBA verification. Lookup joins assume unique organization/city IDs; check these constraints to avoid multiplying trip rows. Python monetary boundaries ultimately use floats for charts; source precision and decimal sums are tested. Existing source observations are not evidence of current live data.

## Complete source

### 1. daily_totals.sql

Authoritative all-history daily baseline

```sql
-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Authoritative daily baseline. SQL dates are stored Gregorian start dates.
-- No active status, geography, completion, amount or duplicate-ID filters.
WITH DailyTotals AS (
    SELECT CAST(t.StartDateTime AS DATE) AS TripDate,
        SUM(CAST(t.TripCost AS DECIMAL(18,2)) * 0.922) AS PassengerFare,
        SUM(CAST(t.TripDriverCost AS DECIMAL(18,2))) AS DriverPayout
    FROM [TooranFramework].[tooranDb].[Trips] AS t
    WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND 1=1
    GROUP BY CAST(t.StartDateTime AS DATE)
)
SELECT TripDate,
    FORMAT(FLOOR(PassengerFare / 10), '#,0') AS PassengerFare,
    FORMAT(FLOOR(DriverPayout / 10), '#,0') AS DriverPayout,
    CAST((PassengerFare - DriverPayout) * 100.0 /
        NULLIF(PassengerFare, 0) AS DECIMAL(10,2)) AS MarginPercent
FROM DailyTotals
ORDER BY TripDate DESC;
```

### 2. trips.sql

Live trip retrieval

```sql
-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Authoritative baseline: PassengerFare = CAST(TripCost AS DECIMAL(18,2)) * 0.922.
-- DriverPayout = CAST(TripDriverCost AS DECIMAL(18,2)); neither stop amount is added.
-- No status, completion, positivity or duplicate-ID exclusions. Optional dates only.
SELECT
    t.Id, t.OrganizationId, t.DriverId, t.StartDateTime, t.EndDateTime,
    o.Name AS OrganizationName, c.Name AS OriginCityName,
    t.Status, t.ServiceType, t.TripType, t.ContractType, t.IsIntercity,
    t.IsExclusive, t.IsPackageTrip, t.OriginCityId, t.HasResidence,
    t.TripCost, t.TripDriverCost, t.StopTime, t.StopTimeCost,
    CAST(t.TripCost AS DECIMAL(18,2)) * 0.922 AS PassengerFare,
    CAST(t.TripCost AS DECIMAL(18,2)) * 0.078 AS FareDeduction,
    CAST(t.TripDriverCost AS DECIMAL(18,2)) AS DriverPayout,
    t.StopTimeDriverCost, t.TotalDistanceByMeter, t.IntercityKilometers,
    t.TotalMlPrice, t.TotalSnapPrice, t.PredictTripCost,
    t.PredictDriverCost, t.PredictTripCostWithoutStopTime,
    t.DriverTotalHours, t.DriverHourlyCost
FROM [TooranFramework].[tooranDb].[Trips] AS t
LEFT JOIN [TooranFramework].[tooranDb].[Organizations] AS o ON o.Id = t.OrganizationId
LEFT JOIN [TooranFramework].[tooranDb].[Cities] AS c ON c.Id = t.OriginCityId
WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND (CAST(? AS datetime2) IS NULL OR t.StartDateTime >= ?)
  AND (CAST(? AS datetime2) IS NULL OR t.StartDateTime < ?)
ORDER BY t.StartDateTime, t.Id;
```

### 3. destinations.sql

Live destination source retrieval

```sql
-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Destination source charges only; the trip baseline establishes no destination fare/payout allocation.
-- One row per destination. NULL date bounds include all matched trip history.
-- Do not join destinations into the trip fact: it multiplies trip money.
SELECT
    d.Id, d.TripId, d.[Order], d.StartDateTime, d.EndDateTime,
    d.DestinationCost, d.DestinationCostWithoutStopTime,
    d.StopTimeDestinationCost, d.StopTime, d.FreeStopTimeByMinutes,
    d.SnapPrice, d.MlPrice, d.DistanceByMeter
FROM [TooranFramework].[tooranDb].[Destinations] AS d
JOIN [TooranFramework].[tooranDb].[Trips] AS t ON t.Id = d.TripId
WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND (CAST(? AS datetime2) IS NULL OR t.StartDateTime >= ?)
  AND (CAST(? AS datetime2) IS NULL OR t.StartDateTime < ?)
ORDER BY d.TripId, d.[Order], d.Id;
```

### 4. retrieval_queries_review.sql

SSMS copies of the two live queries

```sql
-- SSMS copy of both live retrieval queries. Amounts are numeric IRR.
-- The application loads all history within business scope; sidebar filters are separate.
DECLARE @StartDate datetime2 = NULL;
DECLARE @EndDate datetime2 = NULL;

-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Authoritative baseline: PassengerFare = CAST(TripCost AS DECIMAL(18,2)) * 0.922.
-- DriverPayout = CAST(TripDriverCost AS DECIMAL(18,2)); neither stop amount is added.
-- No status, completion, positivity or duplicate-ID exclusions. Optional dates only.
SELECT
    t.Id, t.OrganizationId, t.DriverId, t.StartDateTime, t.EndDateTime,
    o.Name AS OrganizationName, c.Name AS OriginCityName,
    t.Status, t.ServiceType, t.TripType, t.ContractType, t.IsIntercity,
    t.IsExclusive, t.IsPackageTrip, t.OriginCityId, t.HasResidence,
    t.TripCost, t.TripDriverCost, t.StopTime, t.StopTimeCost,
    CAST(t.TripCost AS DECIMAL(18,2)) * 0.922 AS PassengerFare,
    CAST(t.TripCost AS DECIMAL(18,2)) * 0.078 AS FareDeduction,
    CAST(t.TripDriverCost AS DECIMAL(18,2)) AS DriverPayout,
    t.StopTimeDriverCost, t.TotalDistanceByMeter, t.IntercityKilometers,
    t.TotalMlPrice, t.TotalSnapPrice, t.PredictTripCost,
    t.PredictDriverCost, t.PredictTripCostWithoutStopTime,
    t.DriverTotalHours, t.DriverHourlyCost
FROM [TooranFramework].[tooranDb].[Trips] AS t
LEFT JOIN [TooranFramework].[tooranDb].[Organizations] AS o ON o.Id = t.OrganizationId
LEFT JOIN [TooranFramework].[tooranDb].[Cities] AS c ON c.Id = t.OriginCityId
WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND (CAST(@StartDate AS datetime2) IS NULL OR t.StartDateTime >= @StartDate)
  AND (CAST(@EndDate AS datetime2) IS NULL OR t.StartDateTime < @EndDate)
ORDER BY t.StartDateTime, t.Id;

-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Destination source charges only; the trip baseline establishes no destination fare/payout allocation.
-- One row per destination. NULL date bounds include all matched trip history.
-- Do not join destinations into the trip fact: it multiplies trip money.
SELECT
    d.Id, d.TripId, d.[Order], d.StartDateTime, d.EndDateTime,
    d.DestinationCost, d.DestinationCostWithoutStopTime,
    d.StopTimeDestinationCost, d.StopTime, d.FreeStopTimeByMinutes,
    d.SnapPrice, d.MlPrice, d.DistanceByMeter
FROM [TooranFramework].[tooranDb].[Destinations] AS d
JOIN [TooranFramework].[tooranDb].[Trips] AS t ON t.Id = d.TripId
WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND (CAST(@StartDate AS datetime2) IS NULL OR t.StartDateTime >= @StartDate)
  AND (CAST(@EndDate AS datetime2) IS NULL OR t.StartDateTime < @EndDate)
ORDER BY d.TripId, d.[Order], d.Id;
```

### 5. daily_contribution_july_2026.sql

Same daily baseline limited to July 2026

```sql
-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Same baseline, limited to July 2026. Formatted totals are floor(sum(IRR)/10).
-- Authoritative daily baseline. SQL dates are stored Gregorian start dates.
-- No active status, geography, completion, amount or duplicate-ID filters.
WITH DailyTotals AS (
    SELECT CAST(t.StartDateTime AS DATE) AS TripDate,
        SUM(CAST(t.TripCost AS DECIMAL(18,2)) * 0.922) AS PassengerFare,
        SUM(CAST(t.TripDriverCost AS DECIMAL(18,2))) AS DriverPayout
    FROM [TooranFramework].[tooranDb].[Trips] AS t
    WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND t.StartDateTime >= CONVERT(datetime2, '20260701', 112)
      AND t.StartDateTime < CONVERT(datetime2, '20260801', 112)
    GROUP BY CAST(t.StartDateTime AS DATE)
)
SELECT TripDate,
    FORMAT(FLOOR(PassengerFare / 10), '#,0') AS PassengerFare,
    FORMAT(FLOOR(DriverPayout / 10), '#,0') AS DriverPayout,
    CAST((PassengerFare - DriverPayout) * 100.0 /
        NULLIF(PassengerFare, 0) AS DECIMAL(10,2)) AS MarginPercent
FROM DailyTotals
ORDER BY TripDate DESC;
```

### 6. check_costs_1405_05_09.sql

Daily, trip and organization/driver investigation for 2026-07-31

```sql
-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Diagnostic for 1405.05.09 / 2026-07-31. Same baseline; no financial eligibility filters.
-- Stop fields are recorded diagnostics only. Source tables are read only.
SET NOCOUNT ON;
DECLARE @DayStart datetime2 = CONVERT(datetime2, '20260731', 112);
DECLARE @DayEnd datetime2 = DATEADD(day, 1, @DayStart);
DECLARE @OrganizationId bigint = NULL;
DECLARE @OriginCityId bigint = NULL;
DECLARE @IsIntercity bit = NULL;

IF OBJECT_ID('tempdb..#DayTrips') IS NOT NULL DROP TABLE #DayTrips;
SELECT t.Id AS TripId, t.OrganizationId, t.DriverId, t.OriginCityId,
    t.StartDateTime, t.EndDateTime, t.Status, t.IsIntercity,
    CAST(t.TripCost AS DECIMAL(18,2)) * 0.922 AS PassengerFare,
    CAST(t.TripDriverCost AS DECIMAL(18,2)) AS DriverPayout,
    t.StopTimeCost AS RecordedStopCharge, t.StopTimeDriverCost AS RecordedStopDriverAmount
INTO #DayTrips
FROM [TooranFramework].[tooranDb].[Trips] AS t
WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND t.StartDateTime >= @DayStart AND t.StartDateTime < @DayEnd
  AND (@OrganizationId IS NULL OR t.OrganizationId = @OrganizationId)
  AND (@OriginCityId IS NULL OR t.OriginCityId = @OriginCityId)
  AND (@IsIntercity IS NULL OR t.IsIntercity = @IsIntercity);

-- 1. Daily sums are independent, matching SQL SUM(NULL) semantics.
SELECT CAST(@DayStart AS DATE) AS TripDate, COUNT_BIG(*) AS SourceRows,
    FLOOR(SUM(PassengerFare) / 10) AS PassengerFareToman,
    FLOOR(SUM(DriverPayout) / 10) AS DriverPayoutToman,
    (SUM(PassengerFare) - SUM(DriverPayout)) / 10 AS ContributionToman,
    CAST((SUM(PassengerFare) - SUM(DriverPayout)) * 100.0 /
        NULLIF(SUM(PassengerFare), 0) AS DECIMAL(10,2)) AS MarginPercent
FROM #DayTrips;

-- 2. Trip detail; no additional stop payout or charge enters contribution.
SELECT *, PassengerFare / 10 AS PassengerFareToman,
    DriverPayout / 10 AS DriverPayoutToman,
    (PassengerFare - DriverPayout) / 10 AS ContributionToman
FROM #DayTrips
ORDER BY PassengerFare - DriverPayout, TripId;

-- 3. Organization / driver breakdown uses the same independent sums.
SELECT OrganizationId, DriverId, COUNT_BIG(*) AS SourceRows,
    FLOOR(SUM(PassengerFare) / 10) AS PassengerFareToman,
    FLOOR(SUM(DriverPayout) / 10) AS DriverPayoutToman,
    (SUM(PassengerFare) - SUM(DriverPayout)) / 10 AS ContributionToman,
    CAST((SUM(PassengerFare) - SUM(DriverPayout)) * 100.0 /
        NULLIF(SUM(PassengerFare), 0) AS DECIMAL(10,2)) AS MarginPercent
FROM #DayTrips GROUP BY OrganizationId, DriverId;

-- 4. Incomplete values remain in source scope; SUM ignores each NULL independently.
SELECT * FROM #DayTrips
WHERE PassengerFare IS NULL OR DriverPayout IS NULL OR EndDateTime IS NULL;
DROP TABLE #DayTrips;
```

### 7. check_destination_contribution_1405_05_09.sql

Trip baseline plus raw destination fields for 2026-07-31

```sql
-- Business scope: exclude organization سرویس تست رایگان (matching trimmed organization name).
-- Destination source review for 1405.05.09 / 2026-07-31.
-- No destination fare/payout allocation or stop-inclusion convention is inferred.
DECLARE @DayStart datetime2 = CONVERT(datetime2, '20260731', 112);
DECLARE @DayEnd datetime2 = DATEADD(day, 1, @DayStart);

-- 1. Baseline trip financial detail; neither stop field enters these amounts.
SELECT t.Id AS TripId, t.OrganizationId, t.DriverId, t.StartDateTime, t.EndDateTime,
    CAST(t.TripCost AS DECIMAL(18,2)) * 0.922 / 10 AS PassengerFareToman,
    CAST(t.TripDriverCost AS DECIMAL(18,2)) / 10 AS DriverPayoutToman,
    (CAST(t.TripCost AS DECIMAL(18,2)) * 0.922 -
        CAST(t.TripDriverCost AS DECIMAL(18,2))) / 10 AS ContributionToman
FROM [TooranFramework].[tooranDb].[Trips] AS t
WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND t.StartDateTime >= @DayStart AND t.StartDateTime < @DayEnd
ORDER BY t.StartDateTime, t.Id;

-- 2. Raw destination fields, selected with EXISTS to avoid multiplying rows.
SELECT d.Id AS DestinationId, d.TripId, d.[Order], d.StartDateTime, d.EndDateTime,
    d.DestinationCost, d.DestinationCostWithoutStopTime, d.StopTimeDestinationCost,
    d.DestinationCostForDriver, d.StopTimeDestinationCostForDriver,
    CAST(NULL AS DECIMAL(18,2)) AS PassengerFare,
    CAST(NULL AS DECIMAL(18,2)) AS DriverPayout,
    CAST(NULL AS DECIMAL(18,2)) AS Contribution
FROM [TooranFramework].[tooranDb].[Destinations] AS d
WHERE EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Trips] AS t
    WHERE NOT EXISTS (SELECT 1 FROM [TooranFramework].[tooranDb].[Organizations] AS excluded_org WHERE excluded_org.Id = t.OrganizationId AND LTRIM(RTRIM(excluded_org.Name)) = N'سرویس تست رایگان')
  AND t.Id = d.TripId AND t.StartDateTime >= @DayStart AND t.StartDateTime < @DayEnd)
ORDER BY d.TripId, d.[Order], d.Id;
```
