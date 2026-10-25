-- =============================================================================
-- CareerSync — Resume-Based Career and Resource Recommendation System
-- Curated Seed Data (seed_data.sql) — 18 Career Catalog Edition
--
-- Target Database: careersync_db
-- Contents: 52 Verified IT skills, 18 curated job roles, 17 learning resources, and 8 certifications.
-- Idempotency: Uses INSERT ... ON DUPLICATE KEY UPDATE to allow safe repeated execution.
-- =============================================================================

USE `careersync_db`;

-- -----------------------------------------------------------------------------
-- 1. Seed Master Skills (52 Curated Skills)
-- -----------------------------------------------------------------------------
INSERT INTO `skills` (`name`, `normalized_name`, `category`) VALUES
  -- Programming Languages
  ('Python', 'python', 'PROGRAMMING_LANGUAGE'),
  ('JavaScript', 'javascript', 'PROGRAMMING_LANGUAGE'),
  ('TypeScript', 'typescript', 'PROGRAMMING_LANGUAGE'),
  ('Java', 'java', 'PROGRAMMING_LANGUAGE'),
  ('C++', 'cpp', 'PROGRAMMING_LANGUAGE'),
  ('SQL', 'sql', 'PROGRAMMING_LANGUAGE'),
  ('HTML5', 'html5', 'PROGRAMMING_LANGUAGE'),
  ('CSS3', 'css3', 'PROGRAMMING_LANGUAGE'),

  -- Frameworks & Libraries
  ('FastAPI', 'fastapi', 'FRAMEWORK_LIBRARY'),
  ('Flask', 'flask', 'FRAMEWORK_LIBRARY'),
  ('Django', 'django', 'FRAMEWORK_LIBRARY'),
  ('React', 'react', 'FRAMEWORK_LIBRARY'),
  ('Node.js', 'nodejs', 'FRAMEWORK_LIBRARY'),
  ('Express.js', 'expressjs', 'FRAMEWORK_LIBRARY'),
  ('Pandas', 'pandas', 'FRAMEWORK_LIBRARY'),
  ('NumPy', 'numpy', 'FRAMEWORK_LIBRARY'),
  ('Tailwind CSS', 'tailwindcss', 'FRAMEWORK_LIBRARY'),
  ('Spring Boot', 'spring-boot', 'FRAMEWORK_LIBRARY'),
  ('React Native', 'react-native', 'FRAMEWORK_LIBRARY'),

  -- Databases
  ('MySQL', 'mysql', 'DATABASE'),
  ('PostgreSQL', 'postgresql', 'DATABASE'),
  ('SQLite', 'sqlite', 'DATABASE'),
  ('MongoDB', 'mongodb', 'DATABASE'),
  ('Redis', 'redis', 'DATABASE'),

  -- Tools & Platforms
  ('Git', 'git', 'TOOL_PLATFORM'),
  ('GitHub', 'github', 'TOOL_PLATFORM'),
  ('Docker', 'docker', 'TOOL_PLATFORM'),
  ('Postman', 'postman', 'TOOL_PLATFORM'),
  ('Linux / Bash', 'linux-bash', 'TOOL_PLATFORM'),
  ('VS Code', 'vscode', 'TOOL_PLATFORM'),
  ('Nginx', 'nginx', 'TOOL_PLATFORM'),
  ('Power BI', 'power-bi', 'TOOL_PLATFORM'),
  ('Tableau', 'tableau', 'TOOL_PLATFORM'),
  ('Selenium', 'selenium', 'TOOL_PLATFORM'),
  ('Figma', 'figma', 'TOOL_PLATFORM'),

  -- Cloud & DevOps
  ('Amazon Web Services (AWS)', 'aws', 'CLOUD_DEVOPS'),
  ('Microsoft Azure', 'azure', 'CLOUD_DEVOPS'),
  ('Google Cloud Platform (GCP)', 'gcp', 'CLOUD_DEVOPS'),
  ('CI/CD Pipelines', 'cicd', 'CLOUD_DEVOPS'),
  ('Kubernetes', 'kubernetes', 'CLOUD_DEVOPS'),

  -- Core Concepts
  ('RESTful APIs', 'restful-apis', 'CORE_CONCEPT'),
  ('Data Structures & Algorithms', 'dsa', 'CORE_CONCEPT'),
  ('Object-Oriented Programming (OOP)', 'oop', 'CORE_CONCEPT'),
  ('Database Normalization', 'db-normalization', 'CORE_CONCEPT'),
  ('Unit Testing', 'unit-testing', 'CORE_CONCEPT'),
  ('Web Security Basics', 'web-security-basics', 'CORE_CONCEPT'),
  ('Network Security', 'network-security', 'CORE_CONCEPT'),
  ('Machine Learning', 'machine-learning', 'CORE_CONCEPT'),
  ('Agile / Scrum', 'agile-scrum', 'CORE_CONCEPT'),

  -- Soft Skills
  ('Technical Communication', 'technical-communication', 'SOFT_SKILL'),
  ('Problem Solving', 'problem-solving', 'SOFT_SKILL'),
  ('Team Collaboration', 'team-collaboration', 'SOFT_SKILL')
ON DUPLICATE KEY UPDATE
  `category` = VALUES(`category`);

-- -----------------------------------------------------------------------------
-- 2. Seed Certification Providers
-- Keyed on UNIQUE KEY `uq_provider_name` (`name`)
-- -----------------------------------------------------------------------------
INSERT INTO `certification_providers` (`name`, `official_url`) VALUES
  ('Python Institute', 'https://pythoninstitute.org'),
  ('Amazon Web Services', 'https://aws.amazon.com/certification/'),
  ('Microsoft', 'https://learn.microsoft.com/credentials/'),
  ('Oracle', 'https://www.oracle.com/education/certification/'),
  ('Linux Foundation', 'https://training.linuxfoundation.org/certification/'),
  ('CompTIA', 'https://www.comptia.org')
ON DUPLICATE KEY UPDATE
  `official_url` = VALUES(`official_url`);

-- -----------------------------------------------------------------------------
-- 3. Seed Standard Certifications (8 Verified Certifications)
-- Keyed on UNIQUE KEY `uq_cert_provider_name` (`provider_id`, `name`)
-- -----------------------------------------------------------------------------
INSERT INTO `certifications` (`provider_id`, `name`, `code`, `level`, `official_url`, `overview`) VALUES
  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Python Institute'),
   'PCEP – Certified Entry-Level Python Programmer', 'PCEP-30-02', 'ENTRY',
   'https://pythoninstitute.org/pcep',
   'Validates fundamental Python programming concepts, data types, flow control, functions, and standard library basics.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Python Institute'),
   'PCAP – Certified Associate in Python Programming', 'PCAP-31-03', 'ASSOCIATE',
   'https://pythoninstitute.org/pcap',
   'Demonstrates confidence in OOP, modules, packages, exceptions, and fundamental data processing in Python.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Amazon Web Services'),
   'AWS Certified Cloud Practitioner', 'CLF-C02', 'ENTRY',
   'https://aws.amazon.com/certification/certified-cloud-practitioner/',
   'Validates foundational understanding of AWS Cloud concepts, security, architecture, pricing, and support.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Microsoft'),
   'Microsoft Certified: Azure Fundamentals', 'AZ-900', 'ENTRY',
   'https://learn.microsoft.com/credentials/certifications/azure-fundamentals/',
   'Demonstrates foundational knowledge of cloud concepts and core Azure architectural services.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Oracle'),
   'Oracle Certified Associate, Java SE Programmer', '1Z0-808', 'ENTRY',
   'https://www.oracle.com/education/certification/java-se-8-programmer-1z0-808.html',
   'Validates fundamental Java programming knowledge, language syntax, OOP design, and array manipulation.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'CompTIA'),
   'CompTIA Security+', 'SY0-701', 'ENTRY',
   'https://www.comptia.org/certifications/security',
   'Validates baseline cybersecurity skills, risk management, threat mitigation, and network security concepts.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Microsoft'),
   'Microsoft Certified: Power BI Data Analyst Associate', 'PL-300', 'ASSOCIATE',
   'https://learn.microsoft.com/en-us/credentials/certifications/data-analyst-associate/',
   'Validates actionable business intelligence delivery using Microsoft Power BI dashboards and data models.'),

  ((SELECT `id` FROM `certification_providers` WHERE `name` = 'Linux Foundation'),
   'Certified Kubernetes Application Developer (CKAD)', 'CKAD', 'ASSOCIATE',
   'https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/',
   'Certifies skills in designing, building, and deploying containerized applications on Kubernetes.')
ON DUPLICATE KEY UPDATE
  `code` = VALUES(`code`),
  `level` = VALUES(`level`),
  `official_url` = VALUES(`official_url`),
  `overview` = VALUES(`overview`);

-- -----------------------------------------------------------------------------
-- 4. Seed 18 Curated Job Roles (Clean Titles)
-- Keyed on `id`
-- -----------------------------------------------------------------------------
INSERT INTO `job_roles` (`id`, `title`, `domain`, `overview`, `experience_level`, `is_active`) VALUES
  (1, 'Python Backend Developer', 'Web Development',
   'Builds RESTful APIs, implements business logic, handles database interactions, and writes unit tests using Python and modern frameworks like FastAPI or Flask.',
   'ENTRY_LEVEL', TRUE),

  (2, 'Frontend Developer', 'Web Development',
   'Designs and maintains responsive, accessible user interfaces using HTML5, CSS3, JavaScript, and modern UI libraries like React.',
   'ENTRY_LEVEL', TRUE),

  (3, 'Full Stack Developer', 'Web Development',
   'Works across frontend UI components and backend server endpoints, integrating RESTful APIs with relational databases.',
   'ENTRY_LEVEL', TRUE),

  (4, 'Data Analyst', 'Data Engineering & Analytics',
   'Cleans, processes, and analyzes datasets using SQL, Python (Pandas, NumPy), and develops summary reports and metrics dashboards.',
   'ENTRY_LEVEL', TRUE),

  (5, 'Cloud / DevOps Engineer', 'Cloud & DevOps',
   'Assists in deploying containerized web services, configuring basic CI/CD automation pipelines, and provisioning cloud computing instances.',
   'ENTRY_LEVEL', TRUE),

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
-- 5. Seed Job Role Required & Preferred Skills (18 Roles)
-- Keyed on UNIQUE KEY `uq_role_skill` (`job_role_id`, `skill_id`)
-- -----------------------------------------------------------------------------

-- Role 1: Python Backend Developer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Python Backend Developer'
  AND s.`normalized_name` IN ('python', 'fastapi', 'sql', 'mysql', 'restful-apis', 'git')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Python Backend Developer'
  AND s.`normalized_name` IN ('docker', 'postgresql', 'unit-testing', 'db-normalization')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 2: Frontend Developer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Frontend Developer'
  AND s.`normalized_name` IN ('javascript', 'html5', 'css3', 'react', 'git')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Frontend Developer'
  AND s.`normalized_name` IN ('typescript', 'tailwindcss', 'restful-apis')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 3: Full Stack Developer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Full Stack Developer'
  AND s.`normalized_name` IN ('javascript', 'python', 'html5', 'css3', 'react', 'mysql', 'restful-apis', 'git')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 4: Data Analyst
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Data Analyst'
  AND s.`normalized_name` IN ('python', 'sql', 'mysql', 'pandas', 'numpy')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'PREFERRED', 0.75
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Data Analyst'
  AND s.`normalized_name` IN ('power-bi', 'problem-solving', 'technical-communication')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

-- Role 5: Cloud / DevOps Engineer
INSERT INTO `job_role_skills` (`job_role_id`, `skill_id`, `importance`, `weight`)
SELECT r.`id`, s.`id`, 'REQUIRED', 1.00
FROM `job_roles` r, `skills` s
WHERE r.`title` = 'Cloud / DevOps Engineer'
  AND s.`normalized_name` IN ('linux-bash', 'git', 'docker', 'aws', 'cicd')
ON DUPLICATE KEY UPDATE `importance` = VALUES(`importance`), `weight` = VALUES(`weight`);

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

-- -----------------------------------------------------------------------------
-- 6. Seed Verified Learning Resources (17 Verified Resources)
-- Keyed on UNIQUE KEY `uq_resource_title` (`title`) & `uq_resource_url` (`url`)
-- -----------------------------------------------------------------------------
INSERT INTO `learning_resources` (`title`, `resource_type`, `platform_name`, `url`, `is_free`, `difficulty_level`) VALUES
  ('The Python Tutorial (Official Documentation)', 'DOCUMENTATION', 'Python Docs',
   'https://docs.python.org/3/tutorial/', TRUE, 'BEGINNER'),

  ('FastAPI Tutorial - User Guide', 'DOCUMENTATION', 'FastAPI Official Docs',
   'https://fastapi.tiangolo.com/tutorial/', TRUE, 'BEGINNER'),

  ('MDN JavaScript Guide', 'DOCUMENTATION', 'MDN Web Docs',
   'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide', TRUE, 'BEGINNER'),

  ('MDN Learn Web Development (HTML & CSS)', 'DOCUMENTATION', 'MDN Web Docs',
   'https://developer.mozilla.org/en-US/docs/Learn', TRUE, 'BEGINNER'),

  ('Responsive Web Design Certification', 'COURSE', 'freeCodeCamp',
   'https://www.freecodecamp.org/learn/2022/responsive-web-design/', TRUE, 'BEGINNER'),

  ('MySQL 8.0 Reference Manual: SQL Statements', 'DOCUMENTATION', 'MySQL Official Docs',
   'https://dev.mysql.com/doc/refman/8.0/en/sql-statements.html', TRUE, 'INTERMEDIATE'),

  ('Pro Git Book (Official 2nd Edition)', 'DOCUMENTATION', 'Git SCM',
   'https://git-scm.com/book/en/v2', TRUE, 'BEGINNER'),

  ('Docker Getting Started Guide', 'TUTORIAL', 'Docker Docs',
   'https://docs.docker.com/get-started/', TRUE, 'BEGINNER'),

  ('AWS Getting Started Resource Center', 'TUTORIAL', 'Amazon Web Services',
   'https://aws.amazon.com/getting-started/', TRUE, 'BEGINNER'),

  ('React Official Quick Start Documentation', 'DOCUMENTATION', 'React Official Docs',
   'https://react.dev/learn', TRUE, 'BEGINNER'),

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
  `resource_type` = VALUES(`resource_type`),
  `platform_name` = VALUES(`platform_name`),
  `url` = VALUES(`url`),
  `is_free` = VALUES(`is_free`),
  `difficulty_level` = VALUES(`difficulty_level`);

-- -----------------------------------------------------------------------------
-- 7. Seed Resource-to-Skill Mappings
-- Keyed on UNIQUE KEY `uq_resource_skill` (`resource_id`, `skill_id`)
-- -----------------------------------------------------------------------------
-- Python Tutorial -> Python, OOP
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'The Python Tutorial (Official Documentation)'
  AND s.`normalized_name` IN ('python', 'oop')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- FastAPI Tutorial -> FastAPI, Python, RESTful APIs
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'FastAPI Tutorial - User Guide'
  AND s.`normalized_name` IN ('fastapi', 'python', 'restful-apis')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- MDN JS Guide -> JavaScript
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'MDN JavaScript Guide'
  AND s.`normalized_name` IN ('javascript')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- MDN Learn -> HTML5, CSS3
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'MDN Learn Web Development (HTML & CSS)'
  AND s.`normalized_name` IN ('html5', 'css3')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- freeCodeCamp Responsive Web Design -> HTML5, CSS3
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Responsive Web Design Certification'
  AND s.`normalized_name` IN ('html5', 'css3')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- MySQL Manual -> MySQL, SQL, Database Normalization
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'MySQL 8.0 Reference Manual: SQL Statements'
  AND s.`normalized_name` IN ('mysql', 'sql', 'db-normalization')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Pro Git Book -> Git, GitHub
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Pro Git Book (Official 2nd Edition)'
  AND s.`normalized_name` IN ('git', 'github')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Docker Guide -> Docker, Linux / Bash
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Docker Getting Started Guide'
  AND s.`normalized_name` IN ('docker', 'linux-bash')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- AWS Getting Started -> AWS
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'AWS Getting Started Resource Center'
  AND s.`normalized_name` IN ('aws')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- React Quick Start -> React, JavaScript
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'React Official Quick Start Documentation'
  AND s.`normalized_name` IN ('react', 'javascript')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Spring Boot Quickstart -> Spring Boot, Java
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Spring Boot Quickstart Guide (Official Documentation)'
  AND s.`normalized_name` IN ('spring-boot', 'java')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Power BI Guided Learning -> Power BI
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Microsoft Power BI Guided Learning & Docs'
  AND s.`normalized_name` IN ('power-bi')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Selenium WebDriver Tutorials -> Selenium, Unit Testing
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Selenium WebDriver Documentation & Tutorials'
  AND s.`normalized_name` IN ('selenium', 'unit-testing')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Kubernetes Basics -> Kubernetes
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Kubernetes Basics & Tutorials (Official)'
  AND s.`normalized_name` IN ('kubernetes')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Figma Learn -> Figma
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Figma Learn: Design Essentials & Tutorials'
  AND s.`normalized_name` IN ('figma')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Machine Learning Crash Course -> Machine Learning
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'Google Machine Learning Crash Course'
  AND s.`normalized_name` IN ('machine-learning')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- React Native Basics -> React Native
INSERT INTO `resource_skills` (`resource_id`, `skill_id`)
SELECT r.`id`, s.`id`
FROM `learning_resources` r, `skills` s
WHERE r.`title` = 'React Native Official Basics Guide'
  AND s.`normalized_name` IN ('react-native')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- -----------------------------------------------------------------------------
-- 8. Seed Certification-to-Skill Mappings
-- Keyed on UNIQUE KEY `uq_cert_skill` (`certification_id`, `skill_id`)
-- -----------------------------------------------------------------------------
-- PCEP -> Python, OOP
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` LIKE 'PCEP%'
  AND s.`normalized_name` IN ('python', 'oop')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- PCAP -> Python, OOP, Data Structures
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` LIKE 'PCAP%'
  AND s.`normalized_name` IN ('python', 'oop', 'dsa')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- AWS Cloud Practitioner -> AWS
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` LIKE 'AWS Certified Cloud Practitioner%'
  AND s.`normalized_name` IN ('aws')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Azure Fundamentals -> Microsoft Azure
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` LIKE 'Microsoft Certified: Azure Fundamentals%'
  AND s.`normalized_name` IN ('azure')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Java OCA -> Java, OOP
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` LIKE 'Oracle Certified Associate%'
  AND s.`normalized_name` IN ('java', 'oop')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- CompTIA Security+ -> Network Security, Web Security Basics
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'CompTIA Security+'
  AND s.`normalized_name` IN ('network-security', 'web-security-basics')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- Power BI Data Analyst Associate -> Power BI
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'Microsoft Certified: Power BI Data Analyst Associate'
  AND s.`normalized_name` IN ('power-bi')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);

-- CKAD -> Kubernetes
INSERT INTO `certification_skills` (`certification_id`, `skill_id`)
SELECT c.`id`, s.`id`
FROM `certifications` c, `skills` s
WHERE c.`name` = 'Certified Kubernetes Application Developer (CKAD)'
  AND s.`normalized_name` IN ('kubernetes')
ON DUPLICATE KEY UPDATE `skill_id` = VALUES(`skill_id`);
