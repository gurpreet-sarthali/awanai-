-- Dataset registry for Phase 9 user-provided CSV datasets.
-- Safe to run multiple times.

USE `askmydata`;

CREATE TABLE IF NOT EXISTS `datasets` (
    `dataset_id` VARCHAR(64) NOT NULL PRIMARY KEY,
    `dataset_name` VARCHAR(255) NOT NULL,
    `original_filename` VARCHAR(255) NOT NULL,
    `internal_table_name` VARCHAR(64) NOT NULL,
    `storage_reference` VARCHAR(255) NULL,
    `row_count` INT NOT NULL DEFAULT 0,
    `column_count` INT NOT NULL DEFAULT 0,
    `status` VARCHAR(32) NOT NULL,
    `is_builtin` TINYINT(1) NOT NULL DEFAULT 0,
    `validation_status` VARCHAR(32) NOT NULL DEFAULT 'unknown',
    `error_message` TEXT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_datasets_internal_table` (`internal_table_name`)
);

CREATE TABLE IF NOT EXISTS `dataset_columns` (
    `dataset_id` VARCHAR(64) NOT NULL,
    `column_name` VARCHAR(128) NOT NULL,
    `original_column_name` VARCHAR(255) NOT NULL,
    `data_type` VARCHAR(64) NOT NULL,
    `nullable` TINYINT(1) NOT NULL DEFAULT 1,
    `description` VARCHAR(255) NULL,
    `position` INT NOT NULL,
    PRIMARY KEY (`dataset_id`, `column_name`),
    CONSTRAINT `fk_dataset_columns_dataset` FOREIGN KEY (`dataset_id`) REFERENCES `datasets` (`dataset_id`) ON DELETE CASCADE
);

INSERT INTO `datasets` (
    `dataset_id`,
    `dataset_name`,
    `original_filename`,
    `internal_table_name`,
    `storage_reference`,
    `row_count`,
    `column_count`,
    `status`,
    `is_builtin`,
    `validation_status`
)
SELECT
    'demo-placement',
    'Demo Placement Dataset',
    'placement.csv',
    'placement',
    NULL,
    COALESCE((SELECT COUNT(*) FROM `placement`), 0),
    COALESCE((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'placement'), 0),
    'READY',
    1,
    'valid'
WHERE NOT EXISTS (SELECT 1 FROM `datasets` WHERE `dataset_id` = 'demo-placement');
