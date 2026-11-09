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
