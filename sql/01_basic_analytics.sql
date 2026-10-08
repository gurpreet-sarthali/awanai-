-- Basic descriptive analytics.
-- Replace `placement` if 00_database_inspection.sql identifies another table name.
USE `askmydata`;

-- 1. Total number of student records.
SELECT COUNT(*) AS total_students FROM `placement`;
-- 2. Number of placed students.
SELECT COUNT(*) AS placed_students FROM `placement` WHERE `Placement` = 'Yes';
-- 3. Number of students who were not placed.
SELECT COUNT(*) AS not_placed_students FROM `placement` WHERE `Placement` = 'No';
-- 4. Number of students with internships.
SELECT COUNT(*) AS students_with_internships FROM `placement` WHERE `Internship_Experience` = 'Yes';
-- 5. Number of students without internships.
SELECT COUNT(*) AS students_without_internships FROM `placement` WHERE `Internship_Experience` = 'No';
-- 6. Minimum CGPA.
SELECT MIN(`CGPA`) AS minimum_cgpa FROM `placement`;
-- 7. Maximum CGPA.
SELECT MAX(`CGPA`) AS maximum_cgpa FROM `placement`;
-- 8. Average CGPA.
SELECT AVG(`CGPA`) AS average_cgpa FROM `placement`;
-- 9. Minimum IQ.
SELECT MIN(`IQ`) AS minimum_iq FROM `placement`;
-- 10. Maximum IQ.
SELECT MAX(`IQ`) AS maximum_iq FROM `placement`;
-- 11. Average IQ.
SELECT AVG(`IQ`) AS average_iq FROM `placement`;
-- 12. Minimum projects completed.
SELECT MIN(`Projects_Completed`) AS minimum_projects_completed FROM `placement`;
-- 13. Maximum projects completed.
SELECT MAX(`Projects_Completed`) AS maximum_projects_completed FROM `placement`;
-- 14. Average projects completed.
SELECT AVG(`Projects_Completed`) AS average_projects_completed FROM `placement`;