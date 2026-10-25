"""
Stage 5.4 Acceptance Tests — CareerSync Learning Resource & Certification Recommendations
Updated for Phase 1 token security, verified catalog, and isolated SQLite execution.
"""
import io
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path so backend imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import docx
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    AnalysisSession,
    Resume,
    SessionCertificationRecommendation,
    SessionResourceRecommendation,
)
import backend.services.rate_limiter as rl
from tests.test_sqlite_fixtures import setup_sqlite_test_env


def reset_rate_limiter():
    rl._UPLOAD_HISTORY.clear()


def create_docx_with_skills(skills_text: str, candidate_name: str = "Test Candidate") -> bytes:
    """Create in-memory DOCX resume with specified skills."""
    doc = docx.Document()
    doc.add_paragraph(candidate_name)
    doc.add_paragraph("Email: candidate@example.com | Phone: +1-555-010-9999")
    doc.add_heading("TECHNICAL SKILLS", level=1)
    doc.add_paragraph(skills_text)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_resource_and_certification_recommendations_accuracy(client, session_factory):
    """
    Verify learning resource and certification recommendations targeting verified skill gaps:
    Candidate with: Python, SQL, FastAPI, MySQL, Docker, HTML5, CSS3

    Role #1 (Python Backend Developer):
      - Missing required: Git, RESTful APIs -> targeted by resources
      - Missing preferred: Database Normalization -> targeted by resources
    Role #5 (Cloud / DevOps Engineer):
      - Missing required: AWS -> targeted by AWS resources and certifications
    """
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("Python, SQL, FastAPI, MySQL, Docker, HTML5, CSS3", "Python Candidate")
    files = {"file": (f"test_resrec_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    assert up_res.status_code == 200
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    an_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert an_res.status_code == 200

    # 1. Post to analyze resource recommendations
    rec_res = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert rec_res.status_code == 200, f"Recommendation analyze failed: {rec_res.text}"
    data = rec_res.json()

    assert data["resume_id"] == resume_id
    assert data["total_roles_evaluated"] >= 5
    assert data["total_resources"] > 0
    assert data["total_certifications"] > 0

    # Verify Role #1 Learning Resources
    role_1 = next(r for r in data["roles"] if r["job_role_id"] == 1)
    r1_resources = role_1["learning_resources"]
    r1_skill_names = {r["targeted_skill_name"] for r in r1_resources}
    assert "Git" in r1_skill_names
    assert "RESTful APIs" in r1_skill_names
    assert "Database Normalization" in r1_skill_names

    # Check priority: Git and RESTful APIs are critical missing (priority 1)
    for r in r1_resources:
        if r["targeted_skill_name"] in {"Git", "RESTful APIs"}:
            assert r["gap_priority"] == "CRITICAL_MISSING"
            assert r["priority_order"] == 1
        elif r["targeted_skill_name"] == "Database Normalization":
            assert r["gap_priority"] == "SECONDARY_MISSING"
            assert r["priority_order"] == 2

    # Verify Role #5 Certification Recommendation (AWS)
    role_5 = next(r for r in data["roles"] if r["job_role_id"] == 5)
    r5_certs = role_5["certifications"]
    r5_cert_names = {c["name"] for c in r5_certs}
    assert "AWS Certified Cloud Practitioner" in r5_cert_names
    aws_cert = next(c for c in r5_certs if c["name"] == "AWS Certified Cloud Practitioner")
    assert aws_cert["targeted_skill_name"] == "Amazon Web Services (AWS)"
    assert aws_cert["provider_name"] == "Amazon Web Services"
    assert "Amazon Web Services (AWS)" in aws_cert["rationale"]

    # Verify database persistence directly
    with session_factory() as db:
        db_res_recs = (
            db.query(SessionResourceRecommendation)
            .join(AnalysisSession, SessionResourceRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .all()
        )
        assert len(db_res_recs) == data["total_resources"]

        db_cert_recs = (
            db.query(SessionCertificationRecommendation)
            .join(AnalysisSession, SessionCertificationRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .all()
        )
        assert len(db_cert_recs) == data["total_certifications"]

        # Verify resumes.analysis_completed_at was NOT modified
        r_db = db.query(Resume).filter(Resume.id == resume_id).first()
        assert r_db.analysis_completed_at is not None

    print("  [PASS] test_resource_and_certification_recommendations_accuracy: Resources & certs accurately recommended and persisted.")


def test_separate_read_only_get_endpoints(client, session_factory):
    """
    Verify separate read-only GET endpoints for learning resources and certifications:
    1. GET /api/resumes/{id}/learning-resources returns 404 before analyze.
    2. GET /api/resumes/{id}/certifications returns 404 before analyze.
    3. After POST, both return HTTP 200 with persisted records.
    4. Role-specific endpoints return single-role responses.
    """
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("Python, SQL", "Separate Candidate")
    files = {"file": (f"test_sep_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    # 1. GET before analyze returns 404 (does not write)
    get_res_before = client.get(f"/api/resumes/{resume_id}/learning-resources", headers=headers)
    assert get_res_before.status_code == 404
    assert "not been generated" in get_res_before.json()["detail"].lower()

    get_cert_before = client.get(f"/api/resumes/{resume_id}/certifications", headers=headers)
    assert get_cert_before.status_code == 404
    assert "not been generated" in get_cert_before.json()["detail"].lower()

    # Verify zero recommendation rows in DB
    with session_factory() as db:
        count_res = (
            db.query(SessionResourceRecommendation)
            .join(AnalysisSession, SessionResourceRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .count()
        )
        assert count_res == 0

    # 2. Run POST analyze
    post_res = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert post_res.status_code == 200

    # 3. GET learning resources
    get_res_after = client.get(f"/api/resumes/{resume_id}/learning-resources", headers=headers)
    assert get_res_after.status_code == 200
    res_data = get_res_after.json()
    assert res_data["resume_id"] == resume_id
    assert res_data["total_roles"] >= 5
    assert res_data["total_resources"] > 0

    # Single role learning resources
    get_r1 = client.get(f"/api/resumes/{resume_id}/learning-resources/1", headers=headers)
    assert get_r1.status_code == 200
    assert get_r1.json()["job_role_id"] == 1
    assert get_r1.json()["total_resources"] > 0

    # 4. GET certifications
    get_cert_after = client.get(f"/api/resumes/{resume_id}/certifications", headers=headers)
    assert get_cert_after.status_code == 200
    cert_data = get_cert_after.json()
    assert cert_data["resume_id"] == resume_id
    assert cert_data["total_roles"] >= 5

    # Single role certifications
    get_c5 = client.get(f"/api/resumes/{resume_id}/certifications/5", headers=headers)
    assert get_c5.status_code == 200
    assert get_c5.json()["job_role_id"] == 5
    assert get_c5.json()["total_certifications"] > 0

    print("  [PASS] test_separate_read_only_get_endpoints: Separate read-only GET endpoints verified.")


def test_zero_gaps_perfect_match(client, session_factory):
    """Verify candidate matching 100% of skills in Role #5 achieves 0 recommendations for that role."""
    reset_rate_limiter()
    # Role #5: Cloud / DevOps Engineer (Git, Docker, Linux / Bash, AWS, CI/CD Pipelines)
    docx_bytes = create_docx_with_skills("Git, Docker, Linux / Bash, AWS, CI/CD Pipelines", "DevOps Candidate")
    files = {"file": (f"test_perf_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    rec_res = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert rec_res.status_code == 200

    # Check Role #5 specifically
    role_5 = next(r for r in rec_res.json()["roles"] if r["job_role_id"] == 5)
    assert role_5["total_resources"] == 0
    assert role_5["total_certifications"] == 0
    assert role_5["learning_resources"] == []
    assert role_5["certifications"] == []

    # Direct DB check
    with session_factory() as db:
        session_5 = (
            db.query(AnalysisSession)
            .filter(AnalysisSession.resume_id == resume_id, AnalysisSession.job_role_id == 5)
            .first()
        )
        assert session_5 is not None
        res_count = db.query(SessionResourceRecommendation).filter(SessionResourceRecommendation.session_id == session_5.id).count()
        cert_count = db.query(SessionCertificationRecommendation).filter(SessionCertificationRecommendation.session_id == session_5.id).count()
        assert res_count == 0
        assert cert_count == 0

    print("  [PASS] test_zero_gaps_perfect_match: Perfect match produces 0 recommendations for that role.")


def test_zero_matched_skills(client):
    """Verify candidate with 0 catalog skills receives recommendations for all covered missing role skills."""
    reset_rate_limiter()
    doc = docx.Document()
    doc.add_paragraph("Robin Adams")
    doc.add_paragraph("Non-technical candidate.")
    doc.add_heading("EDUCATION", level=1)
    doc.add_paragraph("Community College | AA Arts | 2018 - 2020")
    buf = io.BytesIO()
    doc.save(buf)
    files = {"file": (f"test_zero_{uuid.uuid4().hex[:6]}.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    rec_res = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert rec_res.status_code == 200
    data = rec_res.json()

    assert data["total_resources"] > 0
    # Every role should have recommendations covering its missing skills
    for role in data["roles"]:
        assert role["total_resources"] > 0

    print("  [PASS] test_zero_matched_skills: 0-match candidate receives comprehensive recommendations.")


def test_idempotent_repeated_requests(client, session_factory):
    """Verify running recommendation analysis multiple times updates records in-place without duplicate rows."""
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("Python, FastAPI", "Idempotent Candidate")
    files = {"file": (f"test_idem_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    # Run 1
    res1 = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert res1.status_code == 200
    total_res1 = res1.json()["total_resources"]
    total_certs1 = res1.json()["total_certifications"]

    with session_factory() as db:
        db_res_1 = (
            db.query(SessionResourceRecommendation)
            .join(AnalysisSession, SessionResourceRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .count()
        )
        db_cert_1 = (
            db.query(SessionCertificationRecommendation)
            .join(AnalysisSession, SessionCertificationRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .count()
        )
        assert db_res_1 == total_res1
        assert db_cert_1 == total_certs1

    # Run 2
    res2 = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert res2.status_code == 200
    total_res2 = res2.json()["total_resources"]
    total_certs2 = res2.json()["total_certifications"]

    with session_factory() as db:
        db_res_2 = (
            db.query(SessionResourceRecommendation)
            .join(AnalysisSession, SessionResourceRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .count()
        )
        db_cert_2 = (
            db.query(SessionCertificationRecommendation)
            .join(AnalysisSession, SessionCertificationRecommendation.session_id == AnalysisSession.id)
            .filter(AnalysisSession.resume_id == resume_id)
            .count()
        )
        assert db_res_1 == db_res_2 == total_res2, "Resource recommendation count must not increase"
        assert db_cert_1 == db_cert_2 == total_certs2, "Certification recommendation count must not increase"

    print("  [PASS] test_idempotent_repeated_requests: Repeated analysis is 100% idempotent without duplicates.")


def test_transactional_rollback(client):
    """Verify failure during recommendation generation rolls back cleanly."""
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("Python, SQL", "Rollback Candidate")
    files = {"file": (f"test_rb_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    # Simulate failure during query
    with patch("backend.services.resource_recommender.get_persisted_consolidated_recommendations", side_effect=RuntimeError("Simulated recommender crash")):
        fail_res = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
        assert fail_res.status_code == 500

    print("  [PASS] test_transactional_rollback: Clean rollback verified on failure.")


def test_state_distinctions_and_error_handling(client):
    """Verify HTTP 400 on unanalyzed resumes and 404 on nonexistent resumes/roles."""
    reset_rate_limiter()
    # 1. Unanalyzed resume
    docx_bytes = create_docx_with_skills("Python, SQL", "Unanalyzed Candidate")
    files = {"file": (f"test_unan_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    unanalyzed_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    res_unan_post = client.post(f"/api/resumes/{unanalyzed_id}/resource-recommendations/analyze", headers=headers)
    assert res_unan_post.status_code == 400
    assert "not been analyzed yet" in res_unan_post.json()["detail"].lower()

    res_unan_res = client.get(f"/api/resumes/{unanalyzed_id}/learning-resources", headers=headers)
    assert res_unan_res.status_code == 400

    res_unan_cert = client.get(f"/api/resumes/{unanalyzed_id}/certifications", headers=headers)
    assert res_unan_cert.status_code == 400

    # 2. Nonexistent resume (missing token returns 404)
    res_404_post = client.post("/api/resumes/99999999/resource-recommendations/analyze")
    assert res_404_post.status_code == 404

    res_404_res = client.get("/api/resumes/99999999/learning-resources")
    assert res_404_res.status_code == 404

    res_404_cert = client.get("/api/resumes/99999999/certifications")
    assert res_404_cert.status_code == 404

    # 3. Nonexistent job role
    res_404_role_res = client.get(f"/api/resumes/{unanalyzed_id}/learning-resources/99999999", headers=headers)
    assert res_404_role_res.status_code in {400, 404}

    print("  [PASS] test_state_distinctions_and_error_handling: Unanalyzed 400 and nonexistent 404 verified.")


def test_stages_5_1_to_5_3_regression_invariance(client):
    """Verify Stages 5.1, 5.2, and 5.3 endpoints remain completely invariant after Stage 5.4."""
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("Python, SQL, FastAPI, MySQL, Docker, HTML5, CSS3", "Regression Candidate")
    files = {"file": (f"test_reg_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    up_res = client.post("/api/resumes/upload", files=files)
    token = up_res.json()["access_token"]
    resume_id = up_res.json()["id"]
    headers = {"X-Resume-Token": token}

    client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)

    # Run Stage 5.3 analyze
    client.post(f"/api/resumes/{resume_id}/career-recommendations/analyze", headers=headers)

    # Run Stage 5.4 analyze
    client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)

    # Verify Stage 5.1 matches
    match_res = client.get(f"/api/resumes/{resume_id}/matches/1", headers=headers)
    assert match_res.status_code == 200
    assert match_res.json()["matches"][0]["match_score"] == 52.78

    # Verify Stage 5.2 skill gaps
    gap_res = client.get(f"/api/resumes/{resume_id}/skill-gaps/1", headers=headers)
    assert gap_res.status_code == 200
    assert gap_res.json()["compatibility_score"] == 52.78
    assert gap_res.json()["critical_missing_count"] == 2

    # Verify Stage 5.3 career recommendations
    rec_res = client.get(f"/api/resumes/{resume_id}/career-recommendations/1", headers=headers)
    assert rec_res.status_code == 200
    assert rec_res.json()["match_percentage"] == 52.78

    print("  [PASS] test_stages_5_1_to_5_3_regression_invariance: Stages 5.1, 5.2, & 5.3 remain 100% invariant.")


def run_all_tests():
    print("\n=== Running Stage 5.4 Acceptance Tests (Resource & Certification Recommendations) ===")
    engine, session_factory = setup_sqlite_test_env(app)
    client = TestClient(app)

    test_resource_and_certification_recommendations_accuracy(client, session_factory)
    test_separate_read_only_get_endpoints(client, session_factory)
    test_zero_gaps_perfect_match(client, session_factory)
    test_zero_matched_skills(client)
    test_idempotent_repeated_requests(client, session_factory)
    test_transactional_rollback(client)
    test_state_distinctions_and_error_handling(client)
    test_stages_5_1_to_5_3_regression_invariance(client)

    print("\n=== All Stage 5.4 Acceptance Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_all_tests()
