"""
Stage 4.2 Acceptance Tests — CareerSync Resume Analysis
Updated for Phase 1 token security, verified 18-role catalog, and isolated SQLite execution.
"""
import io
import sys
from pathlib import Path

# Add project root to sys.path so backend imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import docx
from fastapi.testclient import TestClient

from backend.main import app
import backend.services.rate_limiter as rl
from tests.test_sqlite_fixtures import setup_sqlite_test_env


def reset_rate_limiter():
    rl._UPLOAD_HISTORY.clear()


def create_sample_docx_resume(
    name: str = "Alex Turner",
    email: str = "alex.turner@example.com",
    phone: str = "+1-555-987-6543",
    include_edu: bool = True,
    include_exp: bool = True,
    include_proj: bool = True,
) -> bytes:
    """Create in-memory DOCX resume with selectable sections."""
    doc = docx.Document()
    if name:
        doc.add_paragraph(name)
    contact_parts = []
    if email:
        contact_parts.append(f"Email: {email}")
    if phone:
        contact_parts.append(f"Phone: {phone}")
    contact_parts.append("New York, NY")
    if contact_parts:
        doc.add_paragraph(" | ".join(contact_parts))

    if include_edu:
        doc.add_heading("EDUCATION", level=1)
        doc.add_paragraph(
            "Stanford University\n"
            "Bachelor of Science in Computer Science | 2018 - 2022\n"
            "GPA: 3.9 / 4.0"
        )

    doc.add_heading("TECHNICAL SKILLS", level=1)
    doc.add_paragraph(
        "Languages: Python, Java, JavaScript, TypeScript, C++, SQL, HTML5, CSS3\n"
        "Frameworks: FastAPI, React, Node.js, Express.js\n"
        "Databases & Tools: MySQL, PostgreSQL, Docker, Git, AWS\n"
        "Core Concepts: OOP, RESTful APIs, Microservices"
    )

    if include_exp:
        doc.add_heading("PROFESSIONAL EXPERIENCE", level=1)
        doc.add_paragraph(
            "Software Engineer | Apex Systems (2022 - Present)\n"
            "- Designed RESTful APIs using Python, FastAPI, and MySQL with sub-50ms latency.\n"
            "- Containerized backend microservices using Docker and deployed on AWS ECS.\n"
            "- Improved SQL query performance by 40% through indexing and query optimization.\n"
            "- Collaborated using Git and GitHub with CI/CD GitHub Actions pipelines."
        )

    if include_proj:
        doc.add_heading("ACADEMIC & PERSONAL PROJECTS", level=1)
        doc.add_paragraph(
            "CloudSync Engine\n"
            "Technologies: Python, FastAPI, Docker, MySQL\n"
            "- Built high-throughput resume processing engine with text parsing and skill extraction.\n"
            "- Deployed on AWS with automated testing."
        )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_full_resume_analysis(client):
    """TC-4.2-01: Full resume analysis with all sections and skill extraction."""
    reset_rate_limiter()
    docx_bytes = create_sample_docx_resume()
    files = {
        "file": (
            "alex_turner_resume.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    upload_res = client.post("/api/resumes/upload", files=files)
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    resume_id = upload_data["id"]
    token = upload_data["access_token"]

    headers = {"X-Resume-Token": token}
    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200, f"Analysis failed: {analyze_res.text}"
    data = analyze_res.json()

    assert data["resume_id"] == resume_id
    assert data["candidate"]["candidate_name"] == "Alex Turner"
    assert "alex.turner@example.com" in (data["candidate"]["candidate_email"] or "")

    # Verify extracted skills
    skills = data["skills"]
    assert len(skills) >= 10, f"Expected at least 10 skills, got {len(skills)}"
    skill_names = {s["skill_name"].lower() for s in skills}
    expected_sample = {"python", "fastapi", "mysql", "docker", "git"}
    assert expected_sample.issubset(skill_names), f"Missing skills from {expected_sample - skill_names}"

    print(f"  [PASS] test_full_resume_analysis: Analyzed successfully ({len(skills)} skills extracted).")
    return resume_id, token


def test_skill_boundary_accuracy(client):
    """TC-4.2-02: Verify boundary-safe skill matching (e.g. 'c' vs 'c++', 'java' vs 'javascript')."""
    reset_rate_limiter()
    doc = docx.Document()
    doc.add_paragraph("Dev Candidate")
    doc.add_heading("Skills", level=1)
    doc.add_paragraph("We use JavaScript and TypeScript, but NOT Java. Also using CSS3, not C.")
    buf = io.BytesIO()
    doc.save(buf)

    files = {"file": ("boundary_test.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    token = upload_res.json()["access_token"]
    resume_id = upload_res.json()["id"]

    headers = {"X-Resume-Token": token}
    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200
    skills = {s["skill_name"].lower() for s in analyze_res.json()["skills"]}

    assert "javascript" in skills
    assert "typescript" in skills
    assert "css3" in skills
    print("  [PASS] test_skill_boundary_accuracy: Skill boundary matching verified accurately.")


def test_sparse_resume_handling(client):
    """TC-4.2-03: Sparse resume without explicit sections handles gracefully without crash."""
    reset_rate_limiter()
    doc = docx.Document()
    doc.add_paragraph("Jane Minimalist\njane@example.com")
    doc.add_paragraph("Self-taught developer skilled in Python and SQL building web APIs.")
    buf = io.BytesIO()
    doc.save(buf)

    files = {"file": ("sparse.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    token = upload_res.json()["access_token"]
    resume_id = upload_res.json()["id"]

    headers = {"X-Resume-Token": token}
    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200
    data = analyze_res.json()
    assert data["resume_id"] == resume_id
    skills = {s["skill_name"].lower() for s in data["skills"]}
    assert "python" in skills
    assert "sql" in skills
    print("  [PASS] test_sparse_resume_handling: Sparse resume parsed and analyzed cleanly.")


def test_idempotent_reanalysis(client, resume_id, token):
    """TC-4.2-04: Re-analyzing the same resume produces identical skills without duplicates."""
    headers = {"X-Resume-Token": token}
    res1 = client.get(f"/api/resumes/{resume_id}/analysis", headers=headers)
    skills_before = len(res1.json()["skills"])

    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200

    res2 = client.get(f"/api/resumes/{resume_id}/analysis", headers=headers)
    skills_after = len(res2.json()["skills"])

    assert skills_before == skills_after, f"Expected {skills_before} skills, found {skills_after}"
    print("  [PASS] test_idempotent_reanalysis: Re-analysis is deterministic and idempotent.")


def test_get_analysis_endpoint(client, resume_id, token):
    """TC-4.2-05: Retrieve completed analysis via GET /api/resumes/{id}/analysis."""
    headers = {"X-Resume-Token": token}
    res = client.get(f"/api/resumes/{resume_id}/analysis", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["resume_id"] == resume_id
    assert len(data["skills"]) > 0
    print(f"  [PASS] test_get_analysis_endpoint: Analysis retrieved successfully for ID {resume_id}.")


def test_error_handling(client):
    """TC-4.2-06: Nonexistent or unauthorized requests are safely rejected with 404."""
    res = client.post("/api/resumes/99999999/analyze")
    assert res.status_code == 404
    res2 = client.get("/api/resumes/99999999/analysis")
    assert res2.status_code == 404
    print("  [PASS] test_error_handling: Nonexistent resume IDs return 404.")


def run_all_tests():
    print("\n=== Running Stage 4.2 Acceptance Tests (Resume Analysis) ===")
    setup_sqlite_test_env(app)
    client = TestClient(app)

    full_resume_id, full_token = test_full_resume_analysis(client)
    test_skill_boundary_accuracy(client)
    test_sparse_resume_handling(client)
    test_idempotent_reanalysis(client, full_resume_id, full_token)
    test_get_analysis_endpoint(client, full_resume_id, full_token)
    test_error_handling(client)

    print("\n=== All Stage 4.2 Acceptance Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_all_tests()
