# CareerSync Database Documentation

This directory contains the relational database definition, catalog data, migration history, and deployment scripts for **CareerSync** (*Resume-Based Career and Resource Recommendation System*).

- **Database Engine**: MySQL 8.0+ / 8.4 LTS / 9.x (InnoDB engine)
- **Local Development Database**: `careersync_db`
- **Default Character Set**: `utf8mb4`
- **Default Collation**: `utf8mb4_unicode_ci`

---

## Catalog Structure & Verified Entity Counts

The active CareerSync career catalog contains 18 comprehensive IT job roles and 52 verified skills across 7 categories. Both the active local development database (`careersync_db`) and the standalone deployment initialization script ([`deploy_init.sql`](file:///d:/CODE/web%20dev/careerSync/database/deploy_init.sql)) have been verified to contain identical, complete catalog records:

| Entity / Table Name | Record Count | Description |
| :--- | :---: | :--- |
| `skills` | **52** | Verified technical skills across 7 categories (Programming, Web, Database, Cloud, etc.) |
| `job_roles` | **18** | High-demand IT roles (Backend, Frontend, Full Stack, Data Analyst, Cloud/DevOps, AI/ML, etc.) |
| `job_role_skills` | **161** | Verified role-skill mappings with weighted importance (REQUIRED / PREFERRED) |
| `certification_providers` | **6** | Industry standard credential providers (AWS, Microsoft, Google, CompTIA, Oracle, Cisco) |
| `certifications` | **8** | Recognized certifications mapped to domain competencies |
| `learning_resources` | **17** | Curated documentation, official tutorials, and verified learning pathways |
| `resource_skills` | **29** | Skill-to-resource mappings for targeted learning |
| `certification_skills` | **13** | Skill-to-certification mappings for targeted credentialing |
| **Total Catalog Records** | **304** | Complete, integrated career and resource recommendation graph |

> [!NOTE]
> **Role-Skill Mapping Discrepancy Note**: The historical count of "59" referenced in early development notes represented the sum of all mappings across three tables in the original 5-role catalog (36 role-skill + 10 resource-skill + 13 cert-skill = 59). In the active 18-role expanded catalog, there are exactly **161** role-skill mappings (`job_role_skills`).

---

## Directory Files

1. [`deploy_init.sql`](file:///d:/CODE/web%20dev/careerSync/database/deploy_init.sql)
   - **Standalone deployment initialization script for a fresh remote deployment database** (e.g., TiDB Cloud, Aiven, or Remote MySQL).
   - Generates all 19 normalized tables in 3NF with CHECK constraints, foreign keys, and cascading rules.
   - Includes Phase 1 `access_token_hash` column and Phase 2 cleanup/retention indexes (`idx_resumes_created_at`).
   - Seeds the full verified 18-role catalog (all 304 records) idempotently.
   - **SAFETY WARNING**: Never run `deploy_init.sql` against the local development database `careersync_db`.

2. [`schema.sql`](file:///d:/CODE/web%20dev/careerSync/database/schema.sql)
   - Original Data Definition Language (DDL) script in 3rd Normal Form (3NF).
   - Defines all 19 normalized tables, primary keys, foreign keys, and indexes.

3. [`seed_data.sql`](file:///d:/CODE/web%20dev/careerSync/database/seed_data.sql)
   - Foundational seed script (5 initial job roles, 42 skills).

4. `migrations/`
   - `001_expand_catalog.sql`: Expansion of skills and resources.
   - `002_expand_to_18_roles.sql`: Migration expanding career catalog to 18 roles and 161 mappings.
   - `003_add_token_hash.sql`: Phase 1 migration adding `access_token_hash` column to `resumes`.

---

## Deployment Database Initialization

When provisioning a separate remote database for deployment:

1. Create a dedicated database (e.g. `careersync_prod_db` or TiDB Cloud cluster).
2. Execute [`deploy_init.sql`](file:///d:/CODE/web%20dev/careerSync/database/deploy_init.sql) directly against that new remote database.
3. Verify record counts using the query below.
4. Set the corresponding credentials (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL=true`) in your production hosting environment.

### Verification Query

```sql
SELECT 'skills' AS table_name, COUNT(*) AS total FROM skills
UNION ALL
SELECT 'job_roles', COUNT(*) FROM job_roles
UNION ALL
SELECT 'job_role_skills', COUNT(*) FROM job_role_skills
UNION ALL
SELECT 'certification_providers', COUNT(*) FROM certification_providers
UNION ALL
SELECT 'certifications', COUNT(*) FROM certifications
UNION ALL
SELECT 'learning_resources', COUNT(*) FROM learning_resources
UNION ALL
SELECT 'resource_skills', COUNT(*) FROM resource_skills
UNION ALL
SELECT 'certification_skills', COUNT(*) FROM certification_skills;
```

Expected output:
- `skills`: 52
- `job_roles`: 18
- `job_role_skills`: 161
- `certification_providers`: 6
- `certifications`: 8
- `learning_resources`: 17
- `resource_skills`: 29
- `certification_skills`: 13
