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
