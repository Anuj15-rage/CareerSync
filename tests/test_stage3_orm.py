"""
Stage 3 Acceptance Tests — CareerSync SQLAlchemy ORM Models & Database Integration
Updated for isolated SQLite execution and current 18-role / 52-skill catalog.
"""
import sys
from pathlib import Path

# Add project root to sys.path so backend imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.main import app, health_check, verify_seeded_data
from backend.models import (
    AnalysisSession,
    CareerRecommendation,
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
    SessionCertificationRecommendation,
    SessionResourceRecommendation,
    Skill,
    SkillGap,
)
from tests.test_sqlite_fixtures import setup_sqlite_test_env

ALL_19_MODELS = [
    Skill,
    CertificationProvider,
    Certification,
    JobRole,
    LearningResource,
    Resume,
    ResumeEducation,
    ResumeProject,
    ResumeExperience,
    ResumeSkill,
    JobRoleSkill,
    ResourceSkill,
    CertificationSkill,
    AnalysisSession,
    SkillGap,
    CareerRecommendation,
    SessionResourceRecommendation,
    SessionCertificationRecommendation,
    ResumeImprovementSuggestion,
]


def test_model_metadata_registration():
    """Verify all 19 models are properly defined and registered with SQLAlchemy Base."""
    assert len(ALL_19_MODELS) == 19, f"Expected 19 models, got {len(ALL_19_MODELS)}"
    valid_tables = {
        "skills",
        "certification_providers",
        "certifications",
        "job_roles",
        "learning_resources",
        "resumes",
        "resume_education",
        "resume_projects",
        "resume_experience",
        "resume_skills",
        "job_role_skills",
        "resource_skills",
        "certification_skills",
        "analysis_sessions",
        "skill_gaps",
        "career_recommendations",
        "session_resource_recommendations",
        "session_certification_recommendations",
        "resume_improvement_suggestions",
    }
    for model in ALL_19_MODELS:
        assert hasattr(model, "__tablename__"), f"Model {model} missing __tablename__"
        assert model.__tablename__ in valid_tables, f"Unknown table name: {model.__tablename__}"
    print("  [PASS] test_model_metadata_registration: All 19 models registered with valid table names.")


def test_live_session_and_seed_counts(session_factory):
    """Verify database session and verified counts of master catalog records in isolated environment."""
    with session_factory() as db:
        skills_count = db.query(Skill).count()
        roles_count = db.query(JobRole).count()
        resources_count = db.query(LearningResource).count()
        certs_count = db.query(Certification).count()
        providers_count = db.query(CertificationProvider).count()
        mappings_count = db.query(JobRoleSkill).count()

        assert skills_count == 52, f"Expected 52 skills, found {skills_count}"
        assert roles_count == 18, f"Expected 18 job roles, found {roles_count}"
        assert resources_count == 17, f"Expected 17 learning resources, found {resources_count}"
        assert certs_count == 8, f"Expected 8 certifications, found {certs_count}"
        assert providers_count == 6, f"Expected 6 providers, found {providers_count}"
        assert mappings_count == 161, f"Expected 161 role-skill mappings, found {mappings_count}"

    print(
        f"  [PASS] test_live_session_and_seed_counts: Catalog counts verified "
        f"({skills_count} skills, {roles_count} roles, {mappings_count} mappings, {resources_count} resources, {certs_count} certs)."
    )


def test_mapping_tables_and_relationships(session_factory):
    """Verify ORM relationships between JobRole, Skill, LearningResource, and Certification."""
    with session_factory() as db:
        role = db.query(JobRole).filter(JobRole.title == "Python Backend Developer").first()
        assert role is not None, "Role 'Python Backend Developer' not found"
        assert len(role.skill_associations) == 10, f"Expected 10 skills mapped to Python Backend Developer, found {len(role.skill_associations)}"

        skill = db.query(Skill).filter(Skill.normalized_name == "python").first()
        assert skill is not None, "Skill 'python' not found"
        assert len(skill.job_role_associations) >= 1, "Expected python skill to be mapped to at least 1 job role"

        resource = db.query(LearningResource).filter(LearningResource.title.like("%Python%")).first()
        assert resource is not None, "Resource for Python not found"
        assert len(resource.skill_associations) >= 1, "Expected resource to have mapped skills"

        cert = db.query(Certification).filter(Certification.name.like("%PCEP%")).first()
        assert cert is not None, "Certification PCEP not found"
        assert cert.provider is not None, "Certification missing provider relationship"
        assert len(cert.skill_associations) >= 1, "Expected certification to have mapped skills"

    print("  [PASS] test_mapping_tables_and_relationships: M2M relationships verified.")


def test_api_endpoints(session_factory):
    """Verify API root, health, and read-only verification endpoints."""
    client = TestClient(app)

    # 1. Root endpoint
    root_resp = client.get("/")
    assert root_resp.status_code == 200

    # 2. Health endpoint
    health_resp = health_check()
    assert health_resp["status"] in ("healthy", "degraded")
    assert "database" in health_resp

    # 3. Seed verification endpoint
    with session_factory() as db:
        verify_resp = verify_seeded_data(db)
        assert verify_resp["status"] == "success"
        assert verify_resp["counts"]["skills"] == 52
        assert verify_resp["counts"]["job_roles"] == 18
        assert verify_resp["counts"]["learning_resources"] == 17
        assert verify_resp["counts"]["certifications"] == 8
        assert verify_resp["counts"]["certification_providers"] == 6
        assert len(verify_resp["samples"]["skills"]) == 3

    print("  [PASS] test_api_endpoints: Root, Health, and Seed Verification endpoints passed.")


def run_all_tests():
    print("\n=== Running Stage 3 Acceptance Tests (ORM Models & Catalog Integrity) ===")
    test_model_metadata_registration()
    engine, session_factory = setup_sqlite_test_env(app)
    test_live_session_and_seed_counts(session_factory)
    test_mapping_tables_and_relationships(session_factory)
    test_api_endpoints(session_factory)
    print("=== All Stage 3 Acceptance Tests Passed ===\n")


if __name__ == "__main__":
    run_all_tests()
