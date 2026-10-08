-- Placement metrics using conditional aggregation and NULL-safe denominators.
USE `askmydata`;

-- 1. Overall placement rate among records with a known Placement value.
SELECT 100.0 * SUM(`Placement` = 'Yes') / NULLIF(SUM(`Placement` IS NOT NULL), 0) AS placement_rate_pct FROM `placement`;
-- 2. Placement count by status.
SELECT `Placement`, COUNT(*) AS student_count FROM `placement` GROUP BY `Placement` ORDER BY `Placement`;
-- 3. Placement rate among students with internships.
SELECT 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS internship_placement_rate_pct
FROM `placement` WHERE `Internship_Experience` = 'Yes';
-- 4. Placement rate among students without internships.
SELECT 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS no_internship_placement_rate_pct
FROM `placement` WHERE `Internship_Experience` = 'No';
-- 5. Average CGPA of placed students.
SELECT AVG(`CGPA`) AS average_cgpa_placed FROM `placement` WHERE `Placement` = 'Yes';
-- 6. Average CGPA of non-placed students.
SELECT AVG(`CGPA`) AS average_cgpa_not_placed FROM `placement` WHERE `Placement` = 'No';
-- 7. Average IQ of placed students.
SELECT AVG(`IQ`) AS average_iq_placed FROM `placement` WHERE `Placement` = 'Yes';
-- 8. Average IQ of non-placed students.
SELECT AVG(`IQ`) AS average_iq_not_placed FROM `placement` WHERE `Placement` = 'No';
-- 9. Average projects completed by placed students.
SELECT AVG(`Projects_Completed`) AS average_projects_placed FROM `placement` WHERE `Placement` = 'Yes';
-- 10. Average projects completed by non-placed students.
SELECT AVG(`Projects_Completed`) AS average_projects_not_placed FROM `placement` WHERE `Placement` = 'No';
-- 11. Average communication score by placement status.
SELECT
    AVG(CASE WHEN `Placement` = 'Yes' THEN `Communication_Skills` END) AS avg_communication_placed,
    AVG(CASE WHEN `Placement` = 'No' THEN `Communication_Skills` END) AS avg_communication_not_placed
FROM `placement`;
-- 12. Average academic performance by placement status.
SELECT
    AVG(CASE WHEN `Placement` = 'Yes' THEN `Academic_Performance` END) AS avg_academic_placed,
    AVG(CASE WHEN `Placement` = 'No' THEN `Academic_Performance` END) AS avg_academic_not_placed
FROM `placement`;