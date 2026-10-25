"""
Stage 5.1 Acceptance Tests — CareerSync Job Matching and Explainable Match Scores
Updated for Phase 1 token security, verified catalog, and isolated SQLite execution.
Includes verification of all 6 analysis-completion states and transactional rollback.
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
    JobRole,
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeSkill,
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


def test_mathematical_scoring_accuracy(client):
    """
    State 2 verification:
    Verify exact weighted scoring formula against Python Backend Developer (Role #1):
    Role has 6 Required @ 1.00 (Python, SQL, FastAPI, MySQL, Git, RESTful APIs) = 6.00
    Role has 4 Preferred @ 0.75 (PostgreSQL, Docker, Database Normalization, Unit Testing) = 3.00
    Total Weight = 9.00

    Candidate has: Python, SQL, FastAPI, MySQL, Docker, HTML5, CSS3
    Matched Required: Python (1.0), SQL (1.0), FastAPI (1.0), MySQL (1.0) = 4.00
    Matched Preferred: Docker (0.75) = 0.75
    Total Matched Weight = 4.75
    Expected Score = round((4.75 / 9.00) * 100, 2) = 52.78%
    Expected Required Match % = round((4.00 / 6.00) * 100, 2) = 66.67%
    """
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("Python, SQL, FastAPI, MySQL, Docker, HTML5, CSS3", "Python Dev Candidate")
    files = {"file": (f"test_backend_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    # Upload
    upload_res = client.post("/api/resumes/upload", files=files)
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    resume_id = upload_data["id"]
    token = upload_data["access_token"]
    headers = {"X-Resume-Token": token}

    # Analyze
    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200
    assert "analyzed_at" in analyze_res.json()

    # Match against Role #1
    match_res = client.get(f"/api/resumes/{resume_id}/matches/1", headers=headers)
    assert match_res.status_code == 200, f"Match failed: {match_res.text}"
    data = match_res.json()

    assert data["resume_id"] == resume_id
    assert data["matched_roles_count"] == 1
    match = data["matches"][0]

    assert match["job_role_id"] == 1
    assert "Backend Developer" in match["job_role_title"]
    assert match["match_score"] == 52.78, f"Expected 52.78, got {match['match_score']}"
    assert match["required_skills_match_percentage"] == 66.67, f"Expected 66.67, got {match['required_skills_match_percentage']}"
    assert match["matched_skills_count"] == 5
    assert match["total_role_skills_count"] == 10

    # Breakdown verification
    bd = match["score_breakdown"]
    assert bd["total_role_weight"] == 9.0
    assert bd["matched_weight"] == 4.75
    assert bd["required_weight_total"] == 6.0
    assert bd["required_weight_matched"] == 4.0
    assert bd["preferred_weight_total"] == 3.0
    assert bd["preferred_weight_matched"] == 0.75

    # Missing skills verification
    missing_req = {s["skill_name"] for s in match["missing_required_skills"]}
    assert missing_req == {"Git", "RESTful APIs"}

    missing_pref = {s["skill_name"] for s in match["missing_preferred_skills"]}
    assert missing_pref == {"PostgreSQL", "Database Normalization", "Unit Testing"}

    assert "52.78%" in match["explanation"]
    print("  [PASS] test_mathematical_scoring_accuracy: Hand-computed math matches API response exactly.")


def test_perfect_match_100_percent(client):
    """Verify candidate possessing all skills of Role #5 achieves 100.00% score."""
    reset_rate_limiter()
    # Role #5: Cloud / DevOps Engineer (Git, Docker, Linux / Bash, AWS, CI/CD Pipelines)
    docx_bytes = create_docx_with_skills("Git, Docker, Linux / Bash, AWS, CI/CD Pipelines", "DevOps Candidate")
    files = {"file": (f"test_devops_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    upload_res = client.post("/api/resumes/upload", files=files)
    assert upload_res.status_code == 200
    token = upload_res.json()["access_token"]
    resume_id = upload_res.json()["id"]
    headers = {"X-Resume-Token": token}

    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200

    match_res = client.get(f"/api/resumes/{resume_id}/matches/5", headers=headers)
    assert match_res.status_code == 200
    data = match_res.json()
    match = data["matches"][0]

    assert match["match_score"] == 100.00
    assert match["required_skills_match_percentage"] == 100.00
    assert match["matched_skills_count"] == 5
    assert match["missing_required_skills"] == []
    assert match["missing_preferred_skills"] == []
    assert "Perfect match!" in match["explanation"]
    print("  [PASS] test_perfect_match_100_percent: 100.00% score achieved and verified.")


def test_zero_match_0_percent(client):
    """Verify candidate with zero skill overlap achieves 0.00% score without errors."""
    reset_rate_limiter()
    # Candidate with frontend styling tested against Data Analyst (Role #4)
    docx_bytes = create_docx_with_skills("HTML5, CSS3, Figma", "Styling Candidate")
    files = {"file": (f"test_zero_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    upload_res = client.post("/api/resumes/upload", files=files)
    assert upload_res.status_code == 200
    token = upload_res.json()["access_token"]
    resume_id = upload_res.json()["id"]
    headers = {"X-Resume-Token": token}

    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200

    match_res = client.get(f"/api/resumes/{resume_id}/matches/4", headers=headers)
    assert match_res.status_code == 200
    data = match_res.json()
    match = data["matches"][0]

    assert match["match_score"] == 0.00
    assert match["required_skills_match_percentage"] == 0.00
    assert match["matched_skills_count"] == 0
    print("  [PASS] test_zero_match_0_percent: 0.00% score handled cleanly without errors.")


def test_all_active_roles_ranking(client):
    """Verify GET /api/resumes/{id}/matches returns all active roles sorted by match score descending."""
    reset_rate_limiter()
    docx_bytes = create_docx_with_skills("JavaScript, React, HTML5, CSS3, Git", "Frontend Candidate")
    files = {"file": (f"test_ranking_{uuid.uuid4().hex[:6]}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    upload_res = client.post("/api/resumes/upload", files=files)
    assert upload_res.status_code == 200
    token = upload_res.json()["access_token"]
    resume_id = upload_res.json()["id"]
    headers = {"X-Resume-Token": token}

    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200

    match_res = client.get(f"/api/resumes/{resume_id}/matches", headers=headers)
    assert match_res.status_code == 200
    data = match_res.json()

    assert data["matched_roles_count"] >= 5
    matches = data["matches"]

    # Verify descending sort order
    scores = [m["match_score"] for m in matches]
    assert scores == sorted(scores, reverse=True), f"Roles not sorted descending: {scores}"

    # Top match should be Frontend Developer
    assert "Frontend Developer" in matches[0]["job_role_title"]
    print("  [PASS] test_all_active_roles_ranking: Roles evaluated and ranked descending.")


def test_all_six_lifecycle_states(client, session_factory):
    """
    Exhaustively verify all six required lifecycle states:
    1. Uploaded but never analyzed -> HTTP 400 with guidance to analyze first.
    2. Successfully analyzed with recognized skills -> HTTP 200 with normal scores.
    3. Successfully analyzed with zero recognized skills but extracted education/experience -> HTTP 200 with 0.00%.
    4. Successfully analyzed with zero records across all four child tables -> HTTP 200 with valid 0.00%.
    5. Nonexistent resume ID -> HTTP 404.
    6. Analysis failure -> transaction rolled back, analysis_completed_at remains None, matches returns HTTP 400;
       and failed re-analysis preserves previously successful analysis_completed_at.
    """
    reset_rate_limiter()
    # -------------------------------------------------------------------------
    # State 1: Uploaded but never analyzed
    # -------------------------------------------------------------------------
    docx_bytes_1 = create_docx_with_skills("Python, FastAPI", "Unanalyzed Candidate")
    files_1 = {"file": (f"test_state1_{uuid.uuid4().hex[:6]}.docx", docx_bytes_1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_1 = client.post("/api/resumes/upload", files=files_1)
    assert upload_1.status_code == 200
    token_1 = upload_1.json()["access_token"]
    res_id_1 = upload_1.json()["id"]
    headers_1 = {"X-Resume-Token": token_1}

    # Calling matching on unanalyzed resume must return 400
    err_match_1 = client.get(f"/api/resumes/{res_id_1}/matches", headers=headers_1)
    assert err_match_1.status_code == 400
    assert "not been analyzed yet" in err_match_1.json()["detail"].lower()

    # Calling get analysis on unanalyzed resume must return 400
    err_analysis_1 = client.get(f"/api/resumes/{res_id_1}/analysis", headers=headers_1)
    assert err_analysis_1.status_code == 400
    assert "not been analyzed yet" in err_analysis_1.json()["detail"].lower()
    print("  [PASS] State 1 verified: Unanalyzed resume returns HTTP 400.")

    # -------------------------------------------------------------------------
    # State 2: Successfully analyzed with recognized skills
    # -------------------------------------------------------------------------
    analyze_2 = client.post(f"/api/resumes/{res_id_1}/analyze", headers=headers_1)
    assert analyze_2.status_code == 200
    assert analyze_2.json()["analyzed_at"] is not None

    match_2 = client.get(f"/api/resumes/{res_id_1}/matches/1", headers=headers_1)
    assert match_2.status_code == 200
    assert match_2.json()["matches"][0]["match_score"] > 0
    print("  [PASS] State 2 verified: Analyzed resume with skills returns HTTP 200 with weighted score.")

    # -------------------------------------------------------------------------
    # State 3: Successfully analyzed with zero recognized skills, but education/experience present
    # -------------------------------------------------------------------------
    reset_rate_limiter()
    doc_3 = docx.Document()
    doc_3.add_paragraph("Jordan Taylor")
    doc_3.add_paragraph("Email: jordan.taylor@example.com | Phone: +1-555-010-8888")
    doc_3.add_heading("EDUCATION", level=1)
    doc_3.add_paragraph("State University\nBachelor of Arts in Philosophy | 2018 - 2022")
    doc_3.add_heading("WORK EXPERIENCE", level=1)
    doc_3.add_paragraph("Community Coordinator\nNonprofit Org | 2022 - Present\n- Coordinated community outreach programs.")
    buf_3 = io.BytesIO()
    doc_3.save(buf_3)
    files_3 = {"file": (f"test_state3_{uuid.uuid4().hex[:6]}.docx", buf_3.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    upload_3 = client.post("/api/resumes/upload", files=files_3)
    assert upload_3.status_code == 200
    token_3 = upload_3.json()["access_token"]
    res_id_3 = upload_3.json()["id"]
    headers_3 = {"X-Resume-Token": token_3}

    analyze_3 = client.post(f"/api/resumes/{res_id_3}/analyze", headers=headers_3)
    assert analyze_3.status_code == 200
    assert len(analyze_3.json()["skills"]) == 0
    assert len(analyze_3.json()["education"]) >= 1
    assert len(analyze_3.json()["experience"]) >= 1

    match_3 = client.get(f"/api/resumes/{res_id_3}/matches/1", headers=headers_3)
    assert match_3.status_code == 200
    assert match_3.json()["matches"][0]["match_score"] == 0.00
    assert match_3.json()["matches"][0]["matched_skills_count"] == 0
    print("  [PASS] State 3 verified: Zero skills with education/experience returns HTTP 200 with 0.00%.")

    # -------------------------------------------------------------------------
    # State 4: Successfully analyzed with zero records across all four child tables
    # -------------------------------------------------------------------------
    reset_rate_limiter()
    doc_4 = docx.Document()
    doc_4.add_paragraph("General Career Overview")
    doc_4.add_paragraph("Looking for general employment opportunities to grow and learn.")
    doc_4.add_paragraph("Responsible, punctual, and adaptable team player.")
    buf_4 = io.BytesIO()
    doc_4.save(buf_4)
    files_4 = {"file": (f"test_state4_{uuid.uuid4().hex[:6]}.docx", buf_4.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    upload_4 = client.post("/api/resumes/upload", files=files_4)
    assert upload_4.status_code == 200
    token_4 = upload_4.json()["access_token"]
    res_id_4 = upload_4.json()["id"]
    headers_4 = {"X-Resume-Token": token_4}

    analyze_4 = client.post(f"/api/resumes/{res_id_4}/analyze", headers=headers_4)
    assert analyze_4.status_code == 200

    # Verify directly in SQLite that all 4 child tables have EXACTLY 0 rows
    with session_factory() as db:
        assert db.query(ResumeSkill).filter(ResumeSkill.resume_id == res_id_4).count() == 0
        assert db.query(ResumeEducation).filter(ResumeEducation.resume_id == res_id_4).count() == 0
        assert db.query(ResumeProject).filter(ResumeProject.resume_id == res_id_4).count() == 0
        assert db.query(ResumeExperience).filter(ResumeExperience.resume_id == res_id_4).count() == 0
        r4 = db.query(Resume).filter(Resume.id == res_id_4).first()
        assert r4.analysis_completed_at is not None, "analysis_completed_at must be populated"

    # Calling matching on this zero-child-record resume MUST succeed with HTTP 200 and 0.00% score
    match_4 = client.get(f"/api/resumes/{res_id_4}/matches", headers=headers_4)
    assert match_4.status_code == 200
    assert match_4.json()["matched_roles_count"] >= 5
    for m in match_4.json()["matches"]:
        assert m["match_score"] == 0.00
        assert m["matched_skills_count"] == 0
    print("  [PASS] State 4 verified: Zero records across all 4 child tables returns HTTP 200 with 0.00%.")

    # -------------------------------------------------------------------------
    # State 5: Resume does not exist
    # -------------------------------------------------------------------------
    res_404_resume = client.get("/api/resumes/99999999/matches")
    assert res_404_resume.status_code == 404
    res_404_single = client.get("/api/resumes/99999999/matches/1")
    assert res_404_single.status_code == 404
    res_404_role = client.get(f"/api/resumes/{res_id_1}/matches/99999999", headers=headers_1)
    assert res_404_role.status_code == 404
    print("  [PASS] State 5 verified: Nonexistent resume or role returns HTTP 404.")

    # -------------------------------------------------------------------------
    # State 6: Analysis failure and transactional rollback
    # -------------------------------------------------------------------------
    reset_rate_limiter()
    docx_bytes_6 = create_docx_with_skills("Python, MySQL", "Crash Candidate")
    files_6 = {"file": (f"test_state6_{uuid.uuid4().hex[:6]}.docx", docx_bytes_6, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_6 = client.post("/api/resumes/upload", files=files_6)
    assert upload_6.status_code == 200
    token_6 = upload_6.json()["access_token"]
    res_id_6 = upload_6.json()["id"]
    headers_6 = {"X-Resume-Token": token_6}

    # 6a. First analysis fails due to an error during analysis
    with patch("backend.services.resume_analyzer.extract_skills_data", side_effect=RuntimeError("Simulated analysis engine error")):
        fail_res = client.post(f"/api/resumes/{res_id_6}/analyze", headers=headers_6)
        assert fail_res.status_code == 500

    # Verify DB: analysis_completed_at MUST remain None
    with session_factory() as db:
        r6 = db.query(Resume).filter(Resume.id == res_id_6).first()
        assert r6.analysis_completed_at is None, "analysis_completed_at must be None after failed analysis"

    # Calling match on failed resume must return HTTP 400
    err_match_6 = client.get(f"/api/resumes/{res_id_6}/matches", headers=headers_6)
    assert err_match_6.status_code == 400

    # 6b. Now run a successful analysis
    ok_analyze_6 = client.post(f"/api/resumes/{res_id_6}/analyze", headers=headers_6)
    assert ok_analyze_6.status_code == 200
    with session_factory() as db:
        r6 = db.query(Resume).filter(Resume.id == res_id_6).first()
        first_completed_at = r6.analysis_completed_at
        assert first_completed_at is not None

    # 6c. Now simulate a failure during RE-ANALYSIS: previous state must be preserved
    with patch("backend.services.resume_analyzer.extract_skills_data", side_effect=RuntimeError("Simulated re-analysis crash")):
        fail_re_res = client.post(f"/api/resumes/{res_id_6}/analyze", headers=headers_6)
        assert fail_re_res.status_code == 500

    # Verify DB: previous analysis_completed_at and child records are preserved
    with session_factory() as db:
        r6_after = db.query(Resume).filter(Resume.id == res_id_6).first()
        assert r6_after.analysis_completed_at == first_completed_at, "Prior analysis_completed_at must be preserved on failed re-analysis"

    # Matching continues to work based on the previously committed successful analysis
    match_re_ok = client.get(f"/api/resumes/{res_id_6}/matches/1", headers=headers_6)
    assert match_re_ok.status_code == 200
    print("  [PASS] State 6 verified: Analysis failure rolls back cleanly; failed re-analysis preserves prior completed analysis.")


def run_all_tests():
    print("\n=== Running Stage 5.1 Acceptance Tests (Job Matching & Explainable Match Scores) ===")
    engine, session_factory = setup_sqlite_test_env(app)
    client = TestClient(app)

    test_mathematical_scoring_accuracy(client)
    test_perfect_match_100_percent(client)
    test_zero_match_0_percent(client)
    test_all_active_roles_ranking(client)
    test_all_six_lifecycle_states(client, session_factory)

    print("\n=== All Stage 5.1 Acceptance Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_all_tests()
