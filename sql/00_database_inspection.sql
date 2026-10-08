-- Phase 2 preflight inspection for database `askmydata`.
-- Run these statements before the analytics files. They do not assume a table name.

USE `askmydata`;

-- Confirm the active database.
SELECT DATABASE() AS current_database;

-- List tables in the active database.
SHOW TABLES;

-- Inspect every table's columns and data types.
SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- After identifying the placement table, replace `placement` below if necessary.
SELECT COUNT(*) AS row_count FROM `placement`;

-- Check NULL counts for the expected placement columns.
SELECT
    SUM(`College_ID` IS NULL) AS college_id_nulls,
    SUM(`IQ` IS NULL) AS iq_nulls,
    SUM(`Prev_Sem_Result` IS NULL) AS prev_sem_result_nulls,
    SUM(`CGPA` IS NULL) AS cgpa_nulls,
    SUM(`Academic_Performance` IS NULL) AS academic_performance_nulls,
    SUM(`Internship_Experience` IS NULL) AS internship_experience_nulls,
    SUM(`Extra_Curricular_Score` IS NULL) AS extra_curricular_score_nulls,
    SUM(`Communication_Skills` IS NULL) AS communication_skills_nulls,
    SUM(`Projects_Completed` IS NULL) AS projects_completed_nulls,
    SUM(`Placement` IS NULL) AS placement_nulls
FROM `placement`;

-- Check distinct values for the two status columns.
SELECT `Internship_Experience`, COUNT(*) AS student_count
FROM `placement`
GROUP BY `Internship_Experience`
ORDER BY `Internship_Experience`;

SELECT `Placement`, COUNT(*) AS student_count
FROM `placement`
GROUP BY `Placement`
ORDER BY `Placement`;

-- Check duplicate College_ID values and their frequency.
SELECT `College_ID`, COUNT(*) AS occurrence_count
FROM `placement`
GROUP BY `College_ID`
HAVING COUNT(*) > 1
ORDER BY occurrence_count DESC, `College_ID`;

-- Check observed ranges for numeric analytics fields.
SELECT
    MIN(`IQ`) AS min_iq, MAX(`IQ`) AS max_iq,
    MIN(`Prev_Sem_Result`) AS min_prev_sem_result, MAX(`Prev_Sem_Result`) AS max_prev_sem_result,
    MIN(`CGPA`) AS min_cgpa, MAX(`CGPA`) AS max_cgpa,
    MIN(`Academic_Performance`) AS min_academic_performance, MAX(`Academic_Performance`) AS max_academic_performance,
    MIN(`Extra_Curricular_Score`) AS min_extra_curricular_score, MAX(`Extra_Curricular_Score`) AS max_extra_curricular_score,
    MIN(`Communication_Skills`) AS min_communication_skills, MAX(`Communication_Skills`) AS max_communication_skills,
    MIN(`Projects_Completed`) AS min_projects_completed, MAX(`Projects_Completed`) AS max_projects_completed
FROM `placement`;