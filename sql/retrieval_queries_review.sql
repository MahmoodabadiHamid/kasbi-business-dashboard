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
