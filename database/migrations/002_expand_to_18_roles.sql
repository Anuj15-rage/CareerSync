-- =============================================================================
-- Migration: 002_expand_to_18_roles.sql
-- Description: Expand CareerSync catalog from 5 to 18 roles, clean role titles,
--              add required catalog skills, map job_role_skills, learning resources,
--              and industry certifications.
-- Idempotent: Can be run multiple times safely.
-- =============================================================================

USE `careersync_db`;

-- -----------------------------------------------------------------------------
-- 1. Clean Up Displayed Titles of Existing 5 Roles
-- -----------------------------------------------------------------------------
UPDATE `job_roles` SET `title` = 'Python Backend Developer' WHERE `id` = 1;
UPDATE `job_roles` SET `title` = 'Frontend Developer' WHERE `id` = 2;
UPDATE `job_roles` SET `title` = 'Full Stack Developer' WHERE `id` = 3;
UPDATE `job_roles` SET `title` = 'Data Analyst' WHERE `id` = 4;
UPDATE `job_roles` SET `title` = 'Cloud / DevOps Engineer' WHERE `id` = 5;

UPDATE `analysis_sessions` SET `target_role_title` = 'Python Backend Developer' WHERE `job_role_id` = 1;
UPDATE `analysis_sessions` SET `target_role_title` = 'Frontend Developer' WHERE `job_role_id` = 2;
UPDATE `analysis_sessions` SET `target_role_title` = 'Full Stack Developer' WHERE `job_role_id` = 3;
UPDATE `analysis_sessions` SET `target_role_title` = 'Data Analyst' WHERE `job_role_id` = 4;
UPDATE `analysis_sessions` SET `target_role_title` = 'Cloud / DevOps Engineer' WHERE `job_role_id` = 5;

-- -----------------------------------------------------------------------------
-- 2. Insert 10 New Curated Catalog Skills (IDs 43 to 52)
-- -----------------------------------------------------------------------------
INSERT INTO `skills` (`name`, `normalized_name`, `category`) VALUES
  ('Spring Boot', 'spring-boot', 'FRAMEWORK_LIBRARY'),
  ('Power BI', 'power-bi', 'TOOL_PLATFORM'),
  ('Tableau', 'tableau', 'TOOL_PLATFORM'),
  ('Selenium', 'selenium', 'TOOL_PLATFORM'),
  ('Kubernetes', 'kubernetes', 'CLOUD_DEVOPS'),
  ('Network Security', 'network-security', 'CORE_CONCEPT'),
  ('Figma', 'figma', 'TOOL_PLATFORM'),
  ('Machine Learning', 'machine-learning', 'CORE_CONCEPT'),
  ('Agile / Scrum', 'agile-scrum', 'CORE_CONCEPT'),
  ('React Native', 'react-native', 'FRAMEWORK_LIBRARY')
ON DUPLICATE KEY UPDATE `category` = VALUES(`category`);

-- -----------------------------------------------------------------------------
-- 3. Insert 13 New Curated Job Roles (IDs 6 to 18)
-- -----------------------------------------------------------------------------
INSERT INTO `job_roles` (`id`, `title`, `domain`, `overview`, `experience_level`, `is_active`) VALUES
  (6, 'Java Developer', 'Software Development',
   'Builds robust server-side applications, enterprise systems, and RESTful APIs using Java, Spring Boot, object-oriented design patterns, and relational databases.',
   'ENTRY_LEVEL', TRUE),

  (7, 'Software Development Engineer (SDE)', 'Software Engineering',
   'Applies computer science fundamentals, data structures, and algorithms to design, implement, and maintain scalable software architectures and high-performance services.',
   'ENTRY_LEVEL', TRUE),

  (8, 'Data Engineer', 'Data Engineering & Analytics',
   'Architects and manages distributed data pipelines, ETL workflows, database infrastructures, and data processing systems to transform raw data for analytics.',
   'ENTRY_LEVEL', TRUE),

  (9, 'Business Intelligence (BI) Analyst', 'Data Engineering & Analytics',
   'Transforms complex corporate datasets into interactive visual dashboards, tracks key performance indicators, and delivers actionable business intelligence insights.',
   'ENTRY_LEVEL', TRUE),

  (10, 'QA Engineer / Software Tester', 'Quality Assurance & Testing',
   'Develops comprehensive test plans, executes manual and functional test cases, identifies software defects, and ensures adherence to quality standards.',
   'ENTRY_LEVEL', TRUE),

  (11, 'Automation Test Engineer', 'Quality Assurance & Testing',
   'Designs, implements, and maintains automated test scripts and testing frameworks, integrating automated testing suites into continuous integration pipelines.',
   'ENTRY_LEVEL', TRUE),

  (12, 'Site Reliability Engineer (SRE)', 'Cloud & DevOps',
   'Ensures continuous availability, system reliability, infrastructure automation, fault tolerance, and observability for mission-critical production environments.',
   'ENTRY_LEVEL', TRUE),

  (13, 'Cybersecurity Analyst', 'Cybersecurity',
   'Protects IT infrastructure, investigates security threats, conducts vulnerability assessments, monitors network traffic, and implements defensive security controls.',
   'ENTRY_LEVEL', TRUE),

  (14, 'UI/UX Designer', 'Product & Design',
   'Designs intuitive user journeys, wireframes, high-fidelity prototypes, and design systems to deliver user-centered, accessible digital experiences.',
   'ENTRY_LEVEL', TRUE),

  (15, 'Machine Learning Engineer', 'AI & Machine Learning',
   'Researches, designs, and deploys machine learning models, statistical learning pipelines, and predictive algorithms using modern ML frameworks.',
   'ENTRY_LEVEL', TRUE),

  (16, 'Business Analyst', 'Business & Management',
   'Analyzes business operations, elicits technical and functional requirements, documents user stories, and aligns product roadmaps with business objectives.',
   'ENTRY_LEVEL', TRUE),

  (17, 'Database Developer / SQL Developer', 'Database Technology',
   'Designs and normalizes database schemas, writes complex SQL queries and stored procedures, optimizes execution plans, and enforces data integrity.',
   'ENTRY_LEVEL', TRUE),

  (18, 'Mobile App Developer', 'Mobile Development',
   'Creates, tests, and deploys high-performance mobile applications for Android and iOS devices, integrating responsive mobile interfaces with backend APIs.',
   'ENTRY_LEVEL', TRUE)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `domain` = VALUES(`domain`),
  `overview` = VALUES(`overview`),
  `experience_level` = VALUES(`experience_level`),
  `is_active` = VALUES(`is_active`);

-- -----------------------------------------------------------------------------
-- 4. Map Required & Preferred Skills for New Job Roles
-- -----------------------------------------------------------------------------

-- Role 6: Java Developer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Java Developer'
  AND s.`normalized_name` IN ('java', 'spring-boot', 'sql', 'oop', 'restful-apis', 'git')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Java Developer'
  AND s.`normalized_name` IN ('mysql', 'postgresql', 'unit-testing', 'dsa')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 7: Software Development Engineer (SDE)
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Software Development Engineer (SDE)'
  AND s.`normalized_name` IN ('dsa', 'oop', 'problem-solving', 'git')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Software Development Engineer (SDE)'
  AND s.`normalized_name` IN ('python', 'java', 'cpp', 'sql', 'unit-testing', 'restful-apis', 'agile-scrum')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 8: Data Engineer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Data Engineer'
  AND s.`normalized_name` IN ('python', 'sql', 'postgresql', 'db-normalization', 'linux-bash')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Data Engineer'
  AND s.`normalized_name` IN ('docker', 'pandas', 'aws', 'git', 'dsa')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 9: Business Intelligence (BI) Analyst
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Business Intelligence (BI) Analyst'
  AND s.`normalized_name` IN ('sql', 'power-bi', 'tableau', 'technical-communication')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Business Intelligence (BI) Analyst'
  AND s.`normalized_name` IN ('mysql', 'db-normalization', 'problem-solving', 'python', 'pandas')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 10: QA Engineer / Software Tester
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'QA Engineer / Software Tester'
  AND s.`normalized_name` IN ('unit-testing', 'postman', 'problem-solving', 'technical-communication')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'QA Engineer / Software Tester'
  AND s.`normalized_name` IN ('sql', 'git', 'selenium', 'agile-scrum', 'web-security-basics')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 11: Automation Test Engineer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Automation Test Engineer'
  AND s.`normalized_name` IN ('selenium', 'unit-testing', 'python', 'postman', 'cicd')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Automation Test Engineer'
  AND s.`normalized_name` IN ('git', 'javascript', 'java', 'restful-apis', 'linux-bash')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 12: Site Reliability Engineer (SRE)
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Site Reliability Engineer (SRE)'
  AND s.`normalized_name` IN ('linux-bash', 'docker', 'kubernetes', 'cicd', 'python')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Site Reliability Engineer (SRE)'
  AND s.`normalized_name` IN ('aws', 'nginx', 'redis', 'web-security-basics', 'problem-solving')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 13: Cybersecurity Analyst
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Cybersecurity Analyst'
  AND s.`normalized_name` IN ('web-security-basics', 'network-security', 'linux-bash', 'problem-solving')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Cybersecurity Analyst'
  AND s.`normalized_name` IN ('python', 'sql', 'technical-communication', 'git', 'docker')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 14: UI/UX Designer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'UI/UX Designer'
  AND s.`normalized_name` IN ('figma', 'html5', 'css3', 'technical-communication')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'UI/UX Designer'
  AND s.`normalized_name` IN ('tailwindcss', 'team-collaboration', 'problem-solving', 'javascript')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 15: Machine Learning Engineer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Machine Learning Engineer'
  AND s.`normalized_name` IN ('python', 'machine-learning', 'pandas', 'numpy', 'dsa')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Machine Learning Engineer'
  AND s.`normalized_name` IN ('docker', 'sql', 'git', 'problem-solving', 'linux-bash')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 16: Business Analyst
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Business Analyst'
  AND s.`normalized_name` IN ('technical-communication', 'problem-solving', 'team-collaboration', 'sql')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Business Analyst'
  AND s.`normalized_name` IN ('agile-scrum', 'db-normalization', 'power-bi', 'restful-apis')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 17: Database Developer / SQL Developer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Database Developer / SQL Developer'
  AND s.`normalized_name` IN ('sql', 'mysql', 'postgresql', 'db-normalization')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Database Developer / SQL Developer'
  AND s.`normalized_name` IN ('python', 'redis', 'sqlite', 'problem-solving', 'linux-bash')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 18: Mobile App Developer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Mobile App Developer'
  AND s.`normalized_name` IN ('react-native', 'javascript', 'restful-apis', 'git')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Mobile App Developer'
  AND s.`normalized_name` IN ('typescript', 'java', 'react', 'unit-testing', 'problem-solving')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Update Data Analyst (ID 4) with Preferred Skills (Power BI, Problem Solving, Communication)
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Data Analyst'
  AND s.`normalized_name` IN ('power-bi', 'problem-solving', 'technical-communication')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- -----------------------------------------------------------------------------
-- 5. Insert Verified Learning Resources for New Technologies
-- -----------------------------------------------------------------------------
INSERT INTO `learning_resources` (`title`, `resource_type`, `platform_name`, `url`, `is_free`, `difficulty_level`) VALUES
  ('Spring Boot Quickstart Guide (Official Documentation)', 'DOCUMENTATION', 'Spring by VMware',
   'https://spring.io/guides/gs/spring-boot/', TRUE, 'BEGINNER'),

  ('Microsoft Power BI Guided Learning & Docs', 'DOCUMENTATION', 'Microsoft Learn',
   'https://learn.microsoft.com/en-us/power-bi/', TRUE, 'BEGINNER'),

  ('Selenium WebDriver Documentation & Tutorials', 'DOCUMENTATION', 'Selenium.dev',
   'https://www.selenium.dev/documentation/webdriver/', TRUE, 'BEGINNER'),

  ('Kubernetes Basics & Tutorials (Official)', 'DOCUMENTATION', 'Kubernetes Docs',
   'https://kubernetes.io/docs/tutorials/kubernetes-basics/', TRUE, 'INTERMEDIATE'),

  ('Figma Learn: Design Essentials & Tutorials', 'COURSE', 'Figma Community',
   'https://help.figma.com/hc/en-us/categories/360002051613-Get-started', TRUE, 'BEGINNER'),

  ('Google Machine Learning Crash Course', 'COURSE', 'Google for Developers',
   'https://developers.google.com/machine-learning/crash-course', TRUE, 'INTERMEDIATE'),

  ('React Native Official Basics Guide', 'DOCUMENTATION', 'React Native Docs',
   'https://reactnative.dev/docs/getting-started', TRUE, 'BEGINNER')
ON DUPLICATE KEY UPDATE
  `platform_name` = VALUES(`platform_name`),
  `url` = VALUES(`url`),
  `is_free` = VALUES(`is_free`),
  `difficulty_level` = VALUES(`difficulty_level`);

-- Map resources to skills (resource_skills table has resource_id, skill_id)
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Spring Boot Quickstart Guide (Official Documentation)' AND s.`normalized_name` = 'spring-boot'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Spring Boot Quickstart Guide (Official Documentation)' AND s.`normalized_name` = 'java'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Microsoft Power BI Guided Learning & Docs' AND s.`normalized_name` = 'power-bi'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Selenium WebDriver Documentation & Tutorials' AND s.`normalized_name` = 'selenium'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Selenium WebDriver Documentation & Tutorials' AND s.`normalized_name` = 'unit-testing'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Kubernetes Basics & Tutorials (Official)' AND s.`normalized_name` = 'kubernetes'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Figma Learn: Design Essentials & Tutorials' AND s.`normalized_name` = 'figma'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Google Machine Learning Crash Course' AND s.`normalized_name` = 'machine-learning'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'React Native Official Basics Guide' AND s.`normalized_name` = 'react-native'
  AND NOT EXISTS (
    SELECT 1 FROM `resource_skills` rs WHERE rs.`resource_id` = r.`id` AND rs.`skill_id` = s.`id`
  );

-- -----------------------------------------------------------------------------
-- 6. Insert Verified Certifications for Expanded Tracks
-- -----------------------------------------------------------------------------
INSERT INTO `certification_providers` (`name`, `official_url`) VALUES
  ('CompTIA', 'https://www.comptia.org')
ON DUPLICATE KEY UPDATE `official_url` = VALUES(`official_url`);

INSERT INTO `certifications` (`provider_id`, `name`, `code`, `level`, `official_url`)
SELECT p.`id`, 'CompTIA Security+', 'SY0-701', 'ENTRY', 'https://www.comptia.org/certifications/security'
FROM `certification_providers` p
WHERE p.`name` = 'CompTIA'
ON DUPLICATE KEY UPDATE `code` = VALUES(`code`), `level` = VALUES(`level`), `official_url` = VALUES(`official_url`);

INSERT INTO `certifications` (`provider_id`, `name`, `code`, `level`, `official_url`)
SELECT p.`id`, 'Microsoft Certified: Power BI Data Analyst Associate', 'PL-300', 'ASSOCIATE', 'https://learn.microsoft.com/en-us/credentials/certifications/data-analyst-associate/'
FROM `certification_providers` p
WHERE p.`name` = 'Microsoft'
ON DUPLICATE KEY UPDATE `code` = VALUES(`code`), `level` = VALUES(`level`), `official_url` = VALUES(`official_url`);

INSERT INTO `certifications` (`provider_id`, `name`, `code`, `level`, `official_url`)
SELECT p.`id`, 'Certified Kubernetes Application Developer (CKAD)', 'CKAD', 'ASSOCIATE', 'https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/'
FROM `certification_providers` p
WHERE p.`name` = 'Linux Foundation'
ON DUPLICATE KEY UPDATE `code` = VALUES(`code`), `level` = VALUES(`level`), `official_url` = VALUES(`official_url`);

-- Map certifications to skills
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'CompTIA Security+' AND s.`normalized_name` = 'network-security'
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'CompTIA Security+' AND s.`normalized_name` = 'web-security-basics'
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'Microsoft Certified: Power BI Data Analyst Associate' AND s.`normalized_name` = 'power-bi'
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'Certified Kubernetes Application Developer (CKAD)' AND s.`normalized_name` = 'kubernetes'
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);
