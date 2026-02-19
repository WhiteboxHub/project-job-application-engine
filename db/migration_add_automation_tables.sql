-- =====================================================
-- Job Application Engine - Database Migration Script
-- Purpose: Add automation tables and modify existing schema
-- Database: new_db (MySQL)
-- =====================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------
-- 1. Create automation_logs table
-- Tracks job application automation results
-- -----------------------------------------------------
DROP TABLE IF EXISTS `automation_logs`;
CREATE TABLE `automation_logs` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `job_listing_id` BIGINT DEFAULT NULL COMMENT 'Reference to job_listing table',
  `candidate_id` INT NOT NULL COMMENT 'Reference to candidate table',
  `job_site_id` INT NOT NULL COMMENT 'Reference to job_sites table',
  `status` ENUM('success', 'failed', 'skipped') NOT NULL,
  `log_file_path` TEXT COMMENT 'Path to detailed log file',
  `error_message` TEXT COMMENT 'Error details if failed',
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX `idx_candidate` (`candidate_id`),
  INDEX `idx_job_site` (`job_site_id`),
  INDEX `idx_timestamp` (`timestamp`),
  INDEX `idx_status` (`status`),
  
  CONSTRAINT `fk_automation_log_listing` 
    FOREIGN KEY (`job_listing_id`) REFERENCES `job_listing`(`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_automation_log_candidate` 
    FOREIGN KEY (`candidate_id`) REFERENCES `candidate`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_automation_log_site` 
    FOREIGN KEY (`job_site_id`) REFERENCES `job_sites`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracks automated job application results';

-- -----------------------------------------------------
-- 2. Modify candidate_marketing table
-- Add automation-specific columns
-- -----------------------------------------------------

-- Check if columns already exist before adding
SET @dbname = DATABASE();
SET @tablename = 'candidate_marketing';

-- Add marketing_flag column
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'marketing_flag');
SET @sql = IF(@col_exists = 0, 
  'ALTER TABLE candidate_marketing ADD COLUMN marketing_flag TINYINT DEFAULT 0 COMMENT ''0=inactive, 1=active for automation''',
  'SELECT ''Column marketing_flag already exists'' AS message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add run_parameters column
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'run_parameters');
SET @sql = IF(@col_exists = 0, 
  'ALTER TABLE candidate_marketing ADD COLUMN run_parameters JSON COMMENT ''Search keywords, location, distance, etc.''',
  'SELECT ''Column run_parameters already exists'' AS message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add scheduled_time column
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'scheduled_time');
SET @sql = IF(@col_exists = 0, 
  'ALTER TABLE candidate_marketing ADD COLUMN scheduled_time TIME DEFAULT ''09:05:00'' COMMENT ''Time to run automation''',
  'SELECT ''Column scheduled_time already exists'' AS message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add is_processed column
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'is_processed');
SET @sql = IF(@col_exists = 0, 
  'ALTER TABLE candidate_marketing ADD COLUMN is_processed BOOLEAN DEFAULT FALSE COMMENT ''Tracks if automation has run''',
  'SELECT ''Column is_processed already exists'' AS message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add last_processed_at column
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'last_processed_at');
SET @sql = IF(@col_exists = 0, 
  'ALTER TABLE candidate_marketing ADD COLUMN last_processed_at TIMESTAMP NULL COMMENT ''Last automation run timestamp''',
  'SELECT ''Column last_processed_at already exists'' AS message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================
-- Verification Queries
-- =====================================================

-- Show automation_logs structure
SELECT 'automation_logs table structure:' AS '';
DESCRIBE automation_logs;

-- Show candidate_marketing structure (new columns)
SELECT '' AS '';
SELECT 'candidate_marketing new columns:' AS '';
SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'candidate_marketing'
  AND COLUMN_NAME IN ('marketing_flag', 'run_parameters', 'scheduled_time', 'is_processed', 'last_processed_at')
ORDER BY ORDINAL_POSITION;

SELECT '' AS '';
SELECT '✅ Migration complete!' AS 'Status';
