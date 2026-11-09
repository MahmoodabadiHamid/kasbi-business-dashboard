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
