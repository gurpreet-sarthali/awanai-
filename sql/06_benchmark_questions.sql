-- Natural-language-to-SQL benchmark set. Each item contains a question and a reference query.
-- Expected table assumption: `placement`; validate with 00_database_inspection.sql first.
USE `askmydata`;

-- 01. What is the total number of students?
SELECT COUNT(*) AS total_students FROM `placement`;
-- 02. How many students were placed?
SELECT COUNT(*) AS placed_students FROM `placement` WHERE `Placement` = 'Yes';
-- 03. How many students were not placed?
SELECT COUNT(*) AS not_placed_students FROM `placement` WHERE `Placement` = 'No';
-- 04. What is the overall placement rate?
SELECT 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct FROM `placement`;
-- 05. How many students had internships?
SELECT COUNT(*) AS students_with_internships FROM `placement` WHERE `Internship_Experience` = 'Yes';
-- 06. Compare placement rates for students with and without internships.
SELECT `Internship_Experience`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct FROM `placement` GROUP BY `Internship_Experience`;
-- 07. What is the placement-rate difference between internship groups?
WITH r AS (SELECT `Internship_Experience`, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS rate FROM `placement` GROUP BY `Internship_Experience`) SELECT MAX(CASE WHEN `Internship_Experience`='Yes' THEN rate END) - MAX(CASE WHEN `Internship_Experience`='No' THEN rate END) AS rate_difference_points FROM r;
-- 08. What is the minimum CGPA?
SELECT MIN(`CGPA`) AS minimum_cgpa FROM `placement`;
-- 09. What is the maximum CGPA?
SELECT MAX(`CGPA`) AS maximum_cgpa FROM `placement`;
-- 10. What is the average CGPA?
SELECT AVG(`CGPA`) AS average_cgpa FROM `placement`;
-- 11. What is the average CGPA of placed students?
SELECT AVG(`CGPA`) AS average_cgpa FROM `placement` WHERE `Placement`='Yes';
-- 12. What is the average CGPA of non-placed students?
SELECT AVG(`CGPA`) AS average_cgpa FROM `placement` WHERE `Placement`='No';
-- 13. What is the average IQ by placement status?
SELECT `Placement`, AVG(`IQ`) AS average_iq FROM `placement` GROUP BY `Placement`;
-- 14. What is the average project count by placement status?
SELECT `Placement`, AVG(`Projects_Completed`) AS average_projects FROM `placement` GROUP BY `Placement`;
-- 15. What is the average communication score by placement status?
SELECT `Placement`, AVG(`Communication_Skills`) AS average_communication FROM `placement` GROUP BY `Placement`;
-- 16. What is the average academic performance by placement status?
SELECT `Placement`, AVG(`Academic_Performance`) AS average_academic_performance FROM `placement` GROUP BY `Placement`;
-- 17. What is the placement rate for each academic performance score?
SELECT `Academic_Performance`, 100.0 * SUM(`Placement`='Yes') / NULLIF(COUNT(`Placement`),0) AS placement_rate_pct FROM `placement` GROUP BY `Academic_Performance`;
-- 18. What is the placement rate for each communication score?
SELECT `Communication_Skills`, 100.0 * SUM(`Placement`='Yes') / NULLIF(COUNT(`Placement`),0) AS placement_rate_pct FROM `placement` GROUP BY `Communication_Skills`;
-- 19. What is the placement rate for each extra-curricular score?
SELECT `Extra_Curricular_Score`, 100.0 * SUM(`Placement`='Yes') / NULLIF(COUNT(`Placement`),0) AS placement_rate_pct FROM `placement` GROUP BY `Extra_Curricular_Score`;
-- 20. What is the placement rate for each project count?
SELECT `Projects_Completed`, 100.0 * SUM(`Placement`='Yes') / NULLIF(COUNT(`Placement`),0) AS placement_rate_pct FROM `placement` GROUP BY `Projects_Completed`;
-- 21. Which CGPA range has the highest placement rate?
SELECT CASE WHEN `CGPA`<6 THEN 'Below 6' WHEN `CGPA`<7 THEN '6 to <7' WHEN `CGPA`<8 THEN '7 to <8' WHEN `CGPA`<9 THEN '8 to <9' ELSE '9+' END AS cgpa_group, 100.0*SUM(`Placement`='Yes')/NULLIF(COUNT(`Placement`),0) AS rate FROM `placement` GROUP BY cgpa_group ORDER BY rate DESC LIMIT 1;
-- 22. Which project group has the highest placement rate?
SELECT CASE WHEN `Projects_Completed`=0 THEN '0' WHEN `Projects_Completed`<=2 THEN '1-2' WHEN `Projects_Completed`<=4 THEN '3-4' ELSE '5+' END AS project_group, 100.0*SUM(`Placement`='Yes')/NULLIF(COUNT(`Placement`),0) AS rate FROM `placement` GROUP BY project_group ORDER BY rate DESC LIMIT 1;
-- 23. Which communication group has the highest placement rate?
SELECT CASE WHEN `Communication_Skills`<=3 THEN '1-3' WHEN `Communication_Skills`<=6 THEN '4-6' ELSE '7-10' END AS communication_group, 100.0*SUM(`Placement`='Yes')/NULLIF(COUNT(`Placement`),0) AS rate FROM `placement` GROUP BY communication_group ORDER BY rate DESC LIMIT 1;
-- 24. Which academic-performance group has the highest placement rate?
SELECT CASE WHEN `Academic_Performance`<=3 THEN '1-3' WHEN `Academic_Performance`<=6 THEN '4-6' ELSE '7-10' END AS academic_group, 100.0*SUM(`Placement`='Yes')/NULLIF(COUNT(`Placement`),0) AS rate FROM `placement` GROUP BY academic_group ORDER BY rate DESC LIMIT 1;
-- 25. Do placed students complete more projects on average?
SELECT AVG(CASE WHEN `Placement`='Yes' THEN `Projects_Completed` END) AS placed_avg, AVG(CASE WHEN `Placement`='No' THEN `Projects_Completed` END) AS not_placed_avg FROM `placement`;
-- 26. Do placed students have higher communication scores on average?
SELECT AVG(CASE WHEN `Placement`='Yes' THEN `Communication_Skills` END) AS placed_avg, AVG(CASE WHEN `Placement`='No' THEN `Communication_Skills` END) AS not_placed_avg FROM `placement`;
-- 27. Do placed students have higher CGPA on average?
SELECT AVG(CASE WHEN `Placement`='Yes' THEN `CGPA` END) AS placed_avg, AVG(CASE WHEN `Placement`='No' THEN `CGPA` END) AS not_placed_avg FROM `placement`;
-- 28. Do placed students have higher IQ on average?
SELECT AVG(CASE WHEN `Placement`='Yes' THEN `IQ` END) AS placed_avg, AVG(CASE WHEN `Placement`='No' THEN `IQ` END) AS not_placed_avg FROM `placement`;
-- 29. Which placement status has the highest average CGPA?
SELECT `Placement`, AVG(`CGPA`) AS average_cgpa FROM `placement` GROUP BY `Placement` ORDER BY average_cgpa DESC LIMIT 1;
-- 30. Are there duplicate College_ID values?
SELECT COUNT(*) - COUNT(DISTINCT `College_ID`) AS duplicate_id_excess FROM `placement`;