"""
CareerSync Isolated SQLite Test Fixtures & Catalog Seeder

Provides a fully isolated, in-memory SQLite database environment for automated testing.
- Enforces SQLite foreign keys via PRAGMA foreign_keys=ON.
- Compiles MySQL-specific column types (LONGTEXT, BIGINT, INTEGER, SMALLINT) for SQLite.
- Seeds the full master catalog (52 skills, 18 roles, 161 role-skill mappings,
  17 learning resources, 29 resource-skill mappings, 6 certification providers,
  8 certifications, 13 certification-skill mappings) directly from deploy_init.sql.
- Overrides FastAPI get_db dependency and cleanup service SessionLocal.
- Guarantees zero connection to and zero mutation of the development MySQL database.
"""

import re
import sys
from pathlib import Path
from typing import Generator, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT, SMALLINT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Compile MySQL-specific column types for SQLite
@compiles(LONGTEXT, "sqlite")
def compile_longtext_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(BIGINT, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"

@compiles(INTEGER, "sqlite")
def compile_integer_sqlite(type_, compiler, **kw):
    return "INTEGER"

@compiles(SMALLINT, "sqlite")
def compile_smallint_sqlite(type_, compiler, **kw):
    return "INTEGER"

from backend.database import Base, get_db
import backend.services.cleanup as cleanup_module
from backend.models import (
    Certification,
    CertificationProvider,
    CertificationSkill,
    JobRole,
    JobRoleSkill,
    LearningResource,
    ResourceSkill,
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeImprovementSuggestion,
    ResumeProject,
    ResumeSkill,
    Skill,
)


def create_isolated_sqlite_engine():
    """Create an in-memory SQLite engine with PRAGMA foreign_keys=ON."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def seed_full_catalog_from_deploy_sql(db: Session, sql_path: Path = None) -> dict:
    """
    Parses database/deploy_init.sql and seeds the complete master catalog
    into the provided database session.
    """
    if sql_path is None:
        sql_path = PROJECT_ROOT / "database" / "deploy_init.sql"

    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # 1. Skills (52)
    skills_block = re.search(r"INSERT INTO `skills`.*?VALUES\s*(.*?)\s*ON DUPLICATE", sql, re.DOTALL).group(1)
    skills_tuples = re.findall(r"\('([^']+)',\s*'([^']+)',\s*'([^']+)'\)", skills_block)
    skill_objs = {norm: Skill(name=name, normalized_name=norm, category=cat) for name, norm, cat in skills_tuples}
    db.add_all(list(skill_objs.values()))
    db.flush()

    # 2. Providers (6)
    prov_block = re.search(r"INSERT INTO `certification_providers`.*?VALUES\s*(.*?)\s*ON DUPLICATE", sql, re.DOTALL).group(1)
    prov_tuples = re.findall(r"\('([^']+)',\s*'([^']+)'\)", prov_block)
    prov_objs = {name: CertificationProvider(name=name, official_url=url) for name, url in prov_tuples}
    db.add_all(list(prov_objs.values()))
    db.flush()

    # 3. Certifications (8)
    cert_block = re.search(r"INSERT INTO `certifications`.*?VALUES\s*(.*?)\s*ON DUPLICATE", sql, re.DOTALL).group(1)
    cert_tuples = re.findall(
        r"SELECT `id` FROM `certification_providers` WHERE `name` = '([^']+)'\),\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'",
        cert_block,
    )
    cert_objs = {
        name: Certification(
            provider_id=prov_objs[prov].id,
            name=name,
            code=code,
            level=lvl,
            official_url=url,
            overview=ov,
        )
        for prov, name, code, lvl, url, ov in cert_tuples
    }
    db.add_all(list(cert_objs.values()))
    db.flush()

    # 4. Job Roles (18)
    roles_block = re.search(r"INSERT INTO `job_roles`.*?VALUES\s*(.*?)\s*ON DUPLICATE", sql, re.DOTALL).group(1)
    roles_tuples = re.findall(
        r"\(\s*(\d+),\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*(?:TRUE|1)\)",
        roles_block,
    )
    role_objs = {
        int(rid): JobRole(
            id=int(rid),
            title=title,
            domain=domain,
            overview=ov,
            experience_level=exp,
            is_active=True,
        )
        for rid, title, domain, ov, exp in roles_tuples
    }
    db.add_all(list(role_objs.values()))
    db.flush()

    # 5. Role-Skill Mappings (161)
    jrs_blocks = re.findall(
        r"INSERT INTO `job_role_skills`.*?SELECT r\.`id`, s\.`id`,\s*'([^']+)',\s*([0-9.]+).*?WHERE (.*?);",
        sql,
        re.DOTALL,
    )
    jrs_objs = []
    for imp, wt, where_clause in jrs_blocks:
        role_title = re.search(r"r\.`title`\s*=\s*'([^']+)'", where_clause).group(1)
        role_id = [r.id for r in role_objs.values() if r.title == role_title][0]
        skills_in_block = re.findall(
            r"'([^']+)'",
            re.search(r"s\.`normalized_name`\s*IN\s*\((.*?)\)", where_clause, re.DOTALL).group(1),
        )
        for s_norm in skills_in_block:
            jrs_objs.append(
                JobRoleSkill(
                    job_role_id=role_id,
                    skill_id=skill_objs[s_norm].id,
                    importance=imp,
                    weight=float(wt),
                )
            )
    db.add_all(jrs_objs)
    db.flush()

    # 6. Learning Resources (17)
    res_block = re.search(r"INSERT INTO `learning_resources`.*?VALUES\s*(.*?)\s*ON DUPLICATE", sql, re.DOTALL).group(1)
    res_tuples = re.findall(
        r"\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*(?:TRUE|1),\s*'([^']+)'\)",
        res_block,
    )
    res_objs = {
        title: LearningResource(
            title=title,
            resource_type=rtype,
            platform_name=plat,
            url=url,
            is_free=True,
            difficulty_level=diff,
        )
        for title, rtype, plat, url, diff in res_tuples
    }
    db.add_all(list(res_objs.values()))
    db.flush()

    # 7. Resource-Skill Mappings (29)
    rs_blocks = re.findall(r"INSERT INTO `resource_skills`.*?WHERE (.*?);", sql, re.DOTALL)
    rs_objs = []
    for where_clause in rs_blocks:
        res_title = re.search(r"r\.`title`\s*=\s*'([^']+)'", where_clause).group(1)
        res_id = res_objs[res_title].id
        skills_in_block = re.findall(
            r"'([^']+)'",
            re.search(r"s\.`normalized_name`\s*IN\s*\((.*?)\)", where_clause, re.DOTALL).group(1),
        )
        for s_norm in skills_in_block:
            rs_objs.append(ResourceSkill(resource_id=res_id, skill_id=skill_objs[s_norm].id))
    db.add_all(rs_objs)

    # 8. Certification-Skill Mappings (13)
    cs_blocks = re.findall(r"INSERT INTO `certification_skills`.*?WHERE (.*?);", sql, re.DOTALL)
    cs_objs = []
    for where_clause in cs_blocks:
        name_clause = re.search(r"c\.`name`\s*(?:LIKE\s*'([^']+)'|=\s*'([^']+)')", where_clause)
        cname_pattern = (name_clause.group(1) or name_clause.group(2)).rstrip("%")
        matched_certs = [c for c in cert_objs.values() if c.name.startswith(cname_pattern)]
        if matched_certs:
            cert_id = matched_certs[0].id
            skills_in_block = re.findall(
                r"'([^']+)'",
                re.search(r"s\.`normalized_name`\s*IN\s*\((.*?)\)", where_clause, re.DOTALL).group(1),
            )
            for s_norm in skills_in_block:
                cs_objs.append(CertificationSkill(certification_id=cert_id, skill_id=skill_objs[s_norm].id))
    db.add_all(cs_objs)
    db.commit()

    return {
        "skills": len(skill_objs),
        "job_roles": len(role_objs),
        "job_role_skills": len(jrs_objs),
        "learning_resources": len(res_objs),
        "resource_skills": len(rs_objs),
        "certification_providers": len(prov_objs),
        "certifications": len(cert_objs),
        "certification_skills": len(cs_objs),
    }


def setup_sqlite_test_env(app):
    """
    Sets up an isolated SQLite test environment:
    - Creates engine and tables
    - Seeds the complete verified master catalog
    - Overrides app.dependency_overrides[get_db] and cleanup_module.SessionLocal
    - Returns (engine, session_factory)
    """
    engine = create_isolated_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    cleanup_module.SessionLocal = TestingSessionLocal

    with TestingSessionLocal() as db:
        seed_full_catalog_from_deploy_sql(db)

    return engine, TestingSessionLocal
