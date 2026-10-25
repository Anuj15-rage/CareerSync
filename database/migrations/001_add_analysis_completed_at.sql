-- =============================================================================
-- Migration 001: Add analysis_completed_at column to resumes table
-- CareerSync — Resume-Based Career and Resource Recommendation System
-- Target: careersync_db
-- =============================================================================

USE `careersync_db`;

ALTER TABLE `resumes`
  ADD COLUMN `analysis_completed_at` TIMESTAMP NULL DEFAULT NULL AFTER `parsing_status`;
