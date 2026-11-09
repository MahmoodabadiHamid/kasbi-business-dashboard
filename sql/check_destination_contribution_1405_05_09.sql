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
