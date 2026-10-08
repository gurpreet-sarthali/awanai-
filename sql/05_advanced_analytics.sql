-- Advanced queries that answer benchmark questions, rather than demonstrating syntax alone.
USE `askmydata`;

-- 1. Which internship group has a statistically larger observed sample and a higher rate than the other?
SELECT `Internship_Experience`, COUNT(*) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Internship_Experience` HAVING COUNT(`Placement`) > 0 ORDER BY placement_rate_pct DESC;

-- 2. Compare internship and non-internship placement rates in one row.
WITH rates AS (
    SELECT `Internship_Experience`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
    FROM `placement` GROUP BY `Internship_Experience`
)
SELECT MAX(CASE WHEN `Internship_Experience` = 'Yes' THEN placement_rate_pct END) AS internship_rate_pct,
       MAX(CASE WHEN `Internship_Experience` = 'No' THEN placement_rate_pct END) AS no_internship_rate_pct,
       MAX(CASE WHEN `Internship_Experience` = 'Yes' THEN placement_rate_pct END) - MAX(CASE WHEN `Internship_Experience` = 'No' THEN placement_rate_pct END) AS rate_difference_points
FROM rates;

-- 3. Rank individual CGPA groups by observed placement rate, breaking ties by sample size.
WITH grouped AS (
    SELECT CASE WHEN `CGPA` < 6 THEN 'Below 6' WHEN `CGPA` < 7 THEN '6 to <7' WHEN `CGPA` < 8 THEN '7 to <8' WHEN `CGPA` < 9 THEN '8 to <9' ELSE '9+' END AS cgpa_group,
           COUNT(`Placement`) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
    FROM `placement` GROUP BY cgpa_group
)
SELECT cgpa_group, student_count, placement_rate_pct, RANK() OVER (ORDER BY placement_rate_pct DESC) AS rate_rank FROM grouped ORDER BY rate_rank, cgpa_group;

-- 4. Compare the observed placement rate for each project count against the overall rate.
WITH overall AS (SELECT 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS overall_rate_pct FROM `placement`)
SELECT p.`Projects_Completed`, COUNT(p.`Placement`) AS student_count,
       100.0 * SUM(p.`Placement` = 'Yes') / NULLIF(COUNT(p.`Placement`), 0) AS group_rate_pct,
       o.overall_rate_pct, 100.0 * SUM(p.`Placement` = 'Yes') / NULLIF(COUNT(p.`Placement`), 0) - o.overall_rate_pct AS difference_points
FROM `placement` p CROSS JOIN overall o GROUP BY p.`Projects_Completed`, o.overall_rate_pct ORDER BY p.`Projects_Completed`;

-- 5. Return groups with both a high rate and at least 100 known-placement records.
SELECT `Communication_Skills`, COUNT(`Placement`) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Communication_Skills` HAVING COUNT(`Placement`) >= 100 ORDER BY placement_rate_pct DESC;

-- 6. Show placed/non-placed averages and their differences using conditional aggregation.
SELECT AVG(CASE WHEN `Placement` = 'Yes' THEN `Projects_Completed` END) AS placed_projects,
       AVG(CASE WHEN `Placement` = 'No' THEN `Projects_Completed` END) AS not_placed_projects,
       AVG(CASE WHEN `Placement` = 'Yes' THEN `Projects_Completed` END) - AVG(CASE WHEN `Placement` = 'No' THEN `Projects_Completed` END) AS project_difference,
       AVG(CASE WHEN `Placement` = 'Yes' THEN `Communication_Skills` END) - AVG(CASE WHEN `Placement` = 'No' THEN `Communication_Skills` END) AS communication_difference,
       AVG(CASE WHEN `Placement` = 'Yes' THEN `CGPA` END) - AVG(CASE WHEN `Placement` = 'No' THEN `CGPA` END) AS cgpa_difference,
       AVG(CASE WHEN `Placement` = 'Yes' THEN `IQ` END) - AVG(CASE WHEN `Placement` = 'No' THEN `IQ` END) AS iq_difference
FROM `placement`;

-- 7. Find status values outside the expected Yes/No domain for data quality review.
SELECT `Placement`, COUNT(*) AS unexpected_count FROM `placement` WHERE `Placement` NOT IN ('Yes', 'No') OR `Placement` IS NULL GROUP BY `Placement`;