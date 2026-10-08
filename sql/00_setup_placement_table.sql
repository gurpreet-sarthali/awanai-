-- Create and import the current College Placement dataset into askmydata.
-- Run from the project root with the native MySQL client and --local-infile=1.
-- This file does not drop existing tables or overwrite existing data.

CREATE DATABASE IF NOT EXISTS `askmydata`;
USE `askmydata`;

CREATE TABLE IF NOT EXISTS `placement` (
    `College_ID` VARCHAR(20) NOT NULL,
    `IQ` INT NULL,
    `Prev_Sem_Result` DECIMAL(5,2) NULL,
    `CGPA` DECIMAL(5,2) NULL,
    `Academic_Performance` TINYINT NULL,
    `Internship_Experience` VARCHAR(10) NULL,
    `Extra_Curricular_Score` TINYINT NULL,
    `Communication_Skills` TINYINT NULL,
    `Projects_Completed` TINYINT NULL,
    `Placement` VARCHAR(10) NULL
);

LOAD DATA LOCAL INFILE 'data/raw/placement.csv'
INTO TABLE `placement`
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 ROWS;
