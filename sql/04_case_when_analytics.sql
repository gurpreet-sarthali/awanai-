-- Category analytics using ranges supported by the observed CSV values.
USE `askmydata`;

-- 1. Placement rate by CGPA group.
SELECT CASE WHEN `CGPA` < 6 THEN 'Below 6' WHEN `CGPA` < 7 THEN '6 to <7' WHEN `CGPA` < 8 THEN '7 to <8' WHEN `CGPA` < 9 THEN '8 to <9' ELSE '9+' END AS cgpa_group,
       COUNT(*) AS student_count, SUM(`Placement` = 'Yes') AS placed_count,
       100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY cgpa_group ORDER BY MIN(`CGPA`);

-- 2. Placement rate by project group for the observed 0-5 project range.
SELECT CASE WHEN `Projects_Completed` = 0 THEN '0' WHEN `Projects_Completed` <= 2 THEN '1-2' WHEN `Projects_Completed` <= 4 THEN '3-4' ELSE '5+' END AS project_group,
       COUNT(*) AS student_count, SUM(`Placement` = 'Yes') AS placed_count,
       100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY project_group ORDER BY MIN(`Projects_Completed`);

-- 3. Placement rate by communication group on the observed 1-10 scale.
SELECT CASE WHEN `Communication_Skills` <= 3 THEN '1-3' WHEN `Communication_Skills` <= 6 THEN '4-6' ELSE '7-10' END AS communication_group,
       COUNT(*) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY communication_group ORDER BY MIN(`Communication_Skills`);

-- 4. Placement rate by academic performance group.
SELECT CASE WHEN `Academic_Performance` <= 3 THEN '1-3' WHEN `Academic_Performance` <= 6 THEN '4-6' ELSE '7-10' END AS academic_group,
       COUNT(*) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY academic_group ORDER BY MIN(`Academic_Performance`);

-- 5. Highest observed CGPA group by placement rate, requiring at least one known Placement.
SELECT cgpa_group, student_count, placement_rate_pct
FROM (
    SELECT CASE WHEN `CGPA` < 6 THEN 'Below 6' WHEN `CGPA` < 7 THEN '6 to <7' WHEN `CGPA` < 8 THEN '7 to <8' WHEN `CGPA` < 9 THEN '8 to <9' ELSE '9+' END AS cgpa_group,
           COUNT(`Placement`) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
    FROM `placement` GROUP BY cgpa_group
) AS grouped_cgpa
ORDER BY placement_rate_pct DESC, student_count DESC LIMIT 1;

-- 6. Highest observed project group by placement rate, requiring at least one known Placement.
SELECT project_group, student_count, placement_rate_pct
FROM (
    SELECT CASE WHEN `Projects_Completed` = 0 THEN '0' WHEN `Projects_Completed` <= 2 THEN '1-2' WHEN `Projects_Completed` <= 4 THEN '3-4' ELSE '5+' END AS project_group,
           COUNT(`Placement`) AS student_count, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
    FROM `placement` GROUP BY project_group
) AS grouped_projects
ORDER BY placement_rate_pct DESC, student_count DESC LIMIT 1;