-- Grouped placement analytics. Rates exclude rows with NULL Placement values.
USE `askmydata`;

-- 1. Placement count by internship status.
SELECT `Internship_Experience`, COUNT(*) AS student_count, SUM(`Placement` = 'Yes') AS placed_count
FROM `placement` GROUP BY `Internship_Experience` ORDER BY `Internship_Experience`;
-- 2. Placement rate by internship status.
SELECT `Internship_Experience`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Internship_Experience` ORDER BY placement_rate_pct DESC;
-- 3. Average CGPA by placement status.
SELECT `Placement`, AVG(`CGPA`) AS average_cgpa FROM `placement` GROUP BY `Placement` ORDER BY `Placement`;
-- 4. Average IQ by placement status.
SELECT `Placement`, AVG(`IQ`) AS average_iq FROM `placement` GROUP BY `Placement` ORDER BY `Placement`;
-- 5. Average projects by placement status.
SELECT `Placement`, AVG(`Projects_Completed`) AS average_projects FROM `placement` GROUP BY `Placement` ORDER BY `Placement`;
-- 6. Placement rate by academic performance.
SELECT `Academic_Performance`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Academic_Performance` ORDER BY `Academic_Performance`;
-- 7. Placement rate by communication score.
SELECT `Communication_Skills`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Communication_Skills` ORDER BY `Communication_Skills`;
-- 8. Placement rate by extra-curricular score.
SELECT `Extra_Curricular_Score`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Extra_Curricular_Score` ORDER BY `Extra_Curricular_Score`;
-- 9. Placement rate by projects completed.
SELECT `Projects_Completed`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY `Projects_Completed` ORDER BY `Projects_Completed`;
-- 10. Placement rate by observed CGPA group.
SELECT CASE WHEN `CGPA` < 6 THEN 'Below 6' WHEN `CGPA` < 7 THEN '6 to <7' WHEN `CGPA` < 8 THEN '7 to <8' WHEN `CGPA` < 9 THEN '8 to <9' ELSE '9+' END AS cgpa_group,
       100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement` GROUP BY cgpa_group ORDER BY MIN(`CGPA`);