-- =============================================================================
-- CareerSync — Resume-Based Career and Resource Recommendation System
-- Database Schema DDL (schema.sql) — Refined
--
-- Target Database: careersync_db
-- Compatibility: MySQL 8.0+ / 8.4 LTS / 9.x
-- Normalization: 3rd Normal Form (3NF)
-- Character Set: utf8mb4 / utf8mb4_unicode_ci
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `careersync_db`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `careersync_db`;

-- -----------------------------------------------------------------------------
-- 1. Master Skills Catalog
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `skills` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `normalized_name` VARCHAR(100) NOT NULL,
  `category` ENUM(
    'PROGRAMMING_LANGUAGE',
    'FRAMEWORK_LIBRARY',
    'DATABASE',
    'TOOL_PLATFORM',
    'CLOUD_DEVOPS',
    'CORE_CONCEPT',
    'SOFT_SKILL'
  ) NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_skills_name` (`name`),
  UNIQUE KEY `uq_skills_normalized` (`normalized_name`),
  INDEX `idx_skills_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Certification Providers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `certification_providers` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(150) NOT NULL,
  `official_url` VARCHAR(500) NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_provider_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. Certifications Catalog
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `certifications` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `provider_id` INT UNSIGNED NOT NULL,
  `name` VARCHAR(255) NOT NULL,
  `code` VARCHAR(50) NULL,
  `level` ENUM('ENTRY', 'ASSOCIATE', 'PROFESSIONAL') NOT NULL DEFAULT 'ENTRY',
  `official_url` VARCHAR(500) NOT NULL,
  `overview` TEXT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cert_provider_name` (`provider_id`, `name`),
  INDEX `idx_cert_provider` (`provider_id`),
  INDEX `idx_cert_level` (`level`),
  CONSTRAINT `fk_cert_provider`
    FOREIGN KEY (`provider_id`) REFERENCES `certification_providers` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. Target Job Roles Catalog (Curated for College Students & Fresh Grads)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `job_roles` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(150) NOT NULL,
  `domain` VARCHAR(100) NOT NULL,
  `overview` TEXT NOT NULL,
  `experience_level` ENUM('INTERNSHIP', 'ENTRY_LEVEL', 'JUNIOR') NOT NULL DEFAULT 'ENTRY_LEVEL',
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_job_role_title` (`title`),
  INDEX `idx_roles_domain` (`domain`),
  INDEX `idx_roles_experience` (`experience_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 5. Verified Learning Resources Catalog
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `learning_resources` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(255) NOT NULL,
  `resource_type` ENUM(
    'DOCUMENTATION',
    'COURSE',
    'TUTORIAL',
    'PRACTICE_PROJECT'
  ) NOT NULL,
  `platform_name` VARCHAR(100) NOT NULL,
  `url` VARCHAR(500) NOT NULL,
  `is_free` BOOLEAN NOT NULL DEFAULT TRUE,
  `difficulty_level` ENUM('BEGINNER', 'INTERMEDIATE', 'ADVANCED') NOT NULL DEFAULT 'BEGINNER',
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_resource_title` (`title`),
  UNIQUE KEY `uq_resource_url` (`url`),
  INDEX `idx_resources_type` (`resource_type`),
  INDEX `idx_resources_platform` (`platform_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 6. Core Uploaded Resumes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resumes` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `file_name` VARCHAR(255) NOT NULL,
  `file_type` VARCHAR(10) NOT NULL,
  `file_size_bytes` INT UNSIGNED NOT NULL,
  `file_hash` VARCHAR(64) NULL,
  `raw_text` LONGTEXT NULL,
  `candidate_name` VARCHAR(150) NULL,
  `candidate_email` VARCHAR(255) NULL,
  `candidate_phone` VARCHAR(50) NULL,
  `parsing_status` ENUM('PENDING', 'PARSED', 'FAILED') NOT NULL DEFAULT 'PENDING',
  `analysis_completed_at` TIMESTAMP NULL DEFAULT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_resumes_created` (`created_at`),
  INDEX `idx_resumes_hash` (`file_hash`),
  INDEX `idx_resumes_status` (`parsing_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 7. Resume Extracted Education
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resume_education` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `resume_id` BIGINT UNSIGNED NOT NULL,
  `institution` VARCHAR(255) NULL,
  `degree` VARCHAR(150) NULL,
  `field_of_study` VARCHAR(150) NULL,
  `start_year` SMALLINT UNSIGNED NULL,
  `end_year` SMALLINT UNSIGNED NULL,
  `grade_or_cgpa` VARCHAR(50) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_edu_resume` (`resume_id`),
  CONSTRAINT `fk_edu_resume`
    FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 8. Resume Extracted Projects
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resume_projects` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `resume_id` BIGINT UNSIGNED NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT NULL,
  `technologies_used` VARCHAR(500) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_proj_resume` (`resume_id`),
  CONSTRAINT `fk_proj_resume`
    FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 9. Resume Extracted Practical Experience / Internships
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resume_experience` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `resume_id` BIGINT UNSIGNED NOT NULL,
  `organization` VARCHAR(255) NULL,
  `role_title` VARCHAR(150) NULL,
  `duration` VARCHAR(100) NULL,
  `description` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_exp_resume` (`resume_id`),
  CONSTRAINT `fk_exp_resume`
    FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 10. M:N Mapping — Skills Extracted from Resume
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resume_skills` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `resume_id` BIGINT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `extraction_source` ENUM(
    'SKILLS_SECTION',
    'PROJECTS',
    'EXPERIENCE',
    'EDUCATION'
  ) NOT NULL DEFAULT 'SKILLS_SECTION',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_resume_skill` (`resume_id`, `skill_id`),
  INDEX `idx_rs_resume` (`resume_id`),
  INDEX `idx_rs_skill` (`skill_id`),
  CONSTRAINT `fk_rs_resume`
    FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_rs_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 11. M:N Mapping — Skills Required by Job Roles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `job_role_skills` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `job_role_id` INT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `importance` ENUM('REQUIRED', 'PREFERRED', 'NICE_TO_HAVE') NOT NULL DEFAULT 'REQUIRED',
  `weight` DECIMAL(3,2) NOT NULL DEFAULT 1.00,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_role_skill` (`job_role_id`, `skill_id`),
  INDEX `idx_jrs_role` (`job_role_id`),
  INDEX `idx_jrs_skill` (`skill_id`),
  CONSTRAINT `fk_jrs_role`
    FOREIGN KEY (`job_role_id`) REFERENCES `job_roles` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_jrs_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `chk_role_skill_weight`
    CHECK (`weight` >= 0.00 AND `weight` <= 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 12. M:N Mapping — Skills Covered by Learning Resources
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resource_skills` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `resource_id` INT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_resource_skill` (`resource_id`, `skill_id`),
  INDEX `idx_resskill_resource` (`resource_id`),
  INDEX `idx_resskill_skill` (`skill_id`),
  CONSTRAINT `fk_resskill_resource`
    FOREIGN KEY (`resource_id`) REFERENCES `learning_resources` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_resskill_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 13. M:N Mapping — Skills Validated by Certifications
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `certification_skills` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `certification_id` INT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cert_skill` (`certification_id`, `skill_id`),
  INDEX `idx_certskill_cert` (`certification_id`),
  INDEX `idx_certskill_skill` (`skill_id`),
  CONSTRAINT `fk_certskill_cert`
    FOREIGN KEY (`certification_id`) REFERENCES `certifications` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_certskill_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 14. Analysis Sessions (Evaluation Run: Resume vs Target Job Specification)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `analysis_sessions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `resume_id` BIGINT UNSIGNED NOT NULL,
  `job_role_id` INT UNSIGNED NULL,
  `target_role_title` VARCHAR(150) NOT NULL,
  `target_job_description` TEXT NOT NULL,
  `compatibility_score` DECIMAL(5,2) NULL,
  `technical_skill_score` DECIMAL(5,2) NULL,
  `education_score` DECIMAL(5,2) NULL,
  `experience_score` DECIMAL(5,2) NULL,
  `keyword_score` DECIMAL(5,2) NULL,
  `methodology_notes` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_session_resume` (`resume_id`),
  INDEX `idx_session_role` (`job_role_id`),
  INDEX `idx_session_created` (`created_at`),
  CONSTRAINT `fk_session_resume`
    FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_session_role`
    FOREIGN KEY (`job_role_id`) REFERENCES `job_roles` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `chk_compatibility_score`
    CHECK (`compatibility_score` IS NULL OR (`compatibility_score` >= 0.00 AND `compatibility_score` <= 100.00)),
  CONSTRAINT `chk_technical_score`
    CHECK (`technical_skill_score` IS NULL OR (`technical_skill_score` >= 0.00 AND `technical_skill_score` <= 100.00)),
  CONSTRAINT `chk_education_score`
    CHECK (`education_score` IS NULL OR (`education_score` >= 0.00 AND `education_score` <= 100.00)),
  CONSTRAINT `chk_experience_score`
    CHECK (`experience_score` IS NULL OR (`experience_score` >= 0.00 AND `experience_score` <= 100.00)),
  CONSTRAINT `chk_keyword_score`
    CHECK (`keyword_score` IS NULL OR (`keyword_score` >= 0.00 AND `keyword_score` <= 100.00))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 15. Skill Gap Analysis Results
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `skill_gaps` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` BIGINT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `gap_priority` ENUM('CRITICAL_MISSING', 'SECONDARY_MISSING', 'UNVERIFIED_CONTEXT') NOT NULL,
  `reason` VARCHAR(255) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_session_gap_skill` (`session_id`, `skill_id`),
  INDEX `idx_gaps_session` (`session_id`),
  INDEX `idx_gaps_skill` (`skill_id`),
  INDEX `idx_gaps_priority` (`gap_priority`),
  CONSTRAINT `fk_gaps_session`
    FOREIGN KEY (`session_id`) REFERENCES `analysis_sessions` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_gaps_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 16. Career Path Recommendations Generated per Session
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `career_recommendations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` BIGINT UNSIGNED NOT NULL,
  `job_role_id` INT UNSIGNED NOT NULL,
  `match_percentage` DECIMAL(5,2) NOT NULL,
  `rationale` TEXT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_session_career_role` (`session_id`, `job_role_id`),
  INDEX `idx_careerrec_session` (`session_id`),
  INDEX `idx_careerrec_role` (`job_role_id`),
  CONSTRAINT `fk_careerrec_session`
    FOREIGN KEY (`session_id`) REFERENCES `analysis_sessions` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_careerrec_role`
    FOREIGN KEY (`job_role_id`) REFERENCES `job_roles` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `chk_career_match_percentage`
    CHECK (`match_percentage` >= 0.00 AND `match_percentage` <= 100.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 17. Learning Resource Recommendations Generated per Session
-- Enforces composite referential integrity with resource_skills mapping
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `session_resource_recommendations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` BIGINT UNSIGNED NOT NULL,
  `resource_id` INT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `priority_order` SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_session_resource_skill` (`session_id`, `resource_id`, `skill_id`),
  INDEX `idx_resrec_session` (`session_id`),
  INDEX `idx_resrec_resource_skill` (`resource_id`, `skill_id`),
  CONSTRAINT `fk_resrec_session`
    FOREIGN KEY (`session_id`) REFERENCES `analysis_sessions` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_resrec_resource_skill`
    FOREIGN KEY (`resource_id`, `skill_id`)
    REFERENCES `resource_skills` (`resource_id`, `skill_id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 18. Certification Recommendations Generated per Session
-- Enforces composite referential integrity with certification_skills mapping
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `session_certification_recommendations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` BIGINT UNSIGNED NOT NULL,
  `certification_id` INT UNSIGNED NOT NULL,
  `skill_id` INT UNSIGNED NOT NULL,
  `rationale` TEXT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_session_cert_skill` (`session_id`, `certification_id`, `skill_id`),
  INDEX `idx_certrec_session` (`session_id`),
  INDEX `idx_certrec_cert_skill` (`certification_id`, `skill_id`),
  CONSTRAINT `fk_certrec_session`
    FOREIGN KEY (`session_id`) REFERENCES `analysis_sessions` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_certrec_cert_skill`
    FOREIGN KEY (`certification_id`, `skill_id`)
    REFERENCES `certification_skills` (`certification_id`, `skill_id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 19. Actionable Resume Improvement Suggestions Generated per Session
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `resume_improvement_suggestions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` BIGINT UNSIGNED NOT NULL,
  `category` ENUM(
    'STRUCTURE',
    'PROJECTS',
    'EXPERIENCE',
    'SKILLS_FORMATTING',
    'KEYWORDS'
  ) NOT NULL,
  `suggestion` TEXT NOT NULL,
  `priority` ENUM('HIGH', 'MEDIUM', 'LOW') NOT NULL DEFAULT 'MEDIUM',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_improve_session` (`session_id`),
  INDEX `idx_improve_priority` (`priority`),
  CONSTRAINT `fk_improve_session`
    FOREIGN KEY (`session_id`) REFERENCES `analysis_sessions` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
