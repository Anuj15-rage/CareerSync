-- =============================================================================
-- Migration 003: Add access_token_hash column to resumes table
-- CareerSync — Resume-Based Career and Resource Recommendation System
-- Target: Target-neutral (applied to whichever database is selected by the connection)
--
-- Documentation for Deployment Database:
-- When deploying to a separate deployment environment (e.g. careersync_deployment_db):
-- 1. Initialize schema: mysql -u <user> -p <deployment_db> < database/schema.sql
-- 2. Seed initial data: mysql -u <user> -p <deployment_db> < database/seed_data.sql
-- 3. Apply migration 002: mysql -u <user> -p <deployment_db> < database/migrations/002_expand_to_18_roles.sql
-- 4. Apply this migration: mysql -u <user> -p <deployment_db> < database/migrations/003_add_access_token_hash.sql
-- =============================================================================

ALTER TABLE `resumes`
  ADD COLUMN `access_token_hash` VARCHAR(64) NULL DEFAULT NULL AFTER `file_hash`,
  ADD INDEX `idx_resumes_access_token_hash` (`access_token_hash`);
