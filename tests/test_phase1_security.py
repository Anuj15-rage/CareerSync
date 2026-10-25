"""
Phase 1 Security & Access Token Test Suite (Isolated In-Memory Database)

Tests:
1. Token generation entropy and SHA-256 hashing.
2. Upload without token generates access token and returns it in response.
3. Access with valid token succeeds (200 OK).
4. Access without token is denied with 404 Not Found.
5. Access with invalid/tampered token is denied with 404 Not Found.
6. Cross-visitor isolation: Token for Visitor A cannot access Visitor B's resume.
7. Authorization enforced across all resume-specific endpoints.
8. Deletion requires valid token; missing or invalid token fails with 404.
9. Successful deletion removes resume and child records while preserving catalog data.
10. 5 MB upload limits: <= 5MB accepted, > 5MB rejected with 400.
11. Unsupported format rejected with 400.
12. End-to-end flow: Upload -> Analyze -> Match -> Skill Gaps -> Career Recs -> Resource Recs -> Delete.
"""

import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"D:\CODE\web dev\careerSync")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import docx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT, SMALLINT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Compile MySQL-specific column types for SQLite in-memory testing
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
from backend.main import app
from backend.models import (
    Certification,
    CertificationProvider,
    JobRole,
    JobRoleSkill,
    LearningResource,
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeSkill,
    Skill,
)
from backend.services.security import (
    generate_access_token,
    hash_access_token,
    store_resume_token_hash,
    get_resume_token_hash,
)

from sqlalchemy import event

# Set up isolated in-memory SQLite database with active foreign key enforcement
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Apply dependency override
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_module():
    """Create all tables and seed minimal catalog data in SQLite."""
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        # Seed test skills
        s1 = Skill(name="Python", normalized_name="python", category="PROGRAMMING_LANGUAGE")
        s2 = Skill(name="SQL", normalized_name="sql", category="DATABASE")
        s3 = Skill(name="FastAPI", normalized_name="fastapi", category="FRAMEWORK_LIBRARY")
        db.add_all([s1, s2, s3])
        db.flush()

        # Seed test job role
        role = JobRole(
            title="Backend Developer",
            domain="Software Engineering",
            overview="Builds backend REST APIs",
            experience_level="ENTRY_LEVEL",
            is_active=True,
        )
        db.add(role)
        db.flush()

        # Map skills to role
        db.add(JobRoleSkill(job_role_id=role.id, skill_id=s1.id, importance="REQUIRED", weight=0.5))
        db.add(JobRoleSkill(job_role_id=role.id, skill_id=s2.id, importance="PREFERRED", weight=0.3))
        db.add(JobRoleSkill(job_role_id=role.id, skill_id=s3.id, importance="NICE_TO_HAVE", weight=0.2))

        # Seed test learning resource
        res = LearningResource(
            title="FastAPI Masterclass",
            resource_type="COURSE",
            platform_name="Coursera",
            url="https://example.com/fastapi",
            difficulty_level="INTERMEDIATE",
            is_free=False,
            is_active=True,
        )
        db.add(res)
        db.commit()


def teardown_module():
    """Drop SQLite tables and restore dependencies."""
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)


def create_sample_docx(text_content: str = None) -> bytes:
    doc = docx.Document()
    doc.add_heading("Alex Rivera", level=1)
    doc.add_paragraph("alex.rivera@example.com | +1-555-0199")
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Python, SQL, FastAPI, Git, Docker")
    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Backend Developer at Acme Corp. Built REST APIs using FastAPI and PostgreSQL.")
    if text_content:
        doc.add_paragraph(text_content)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# 1. Cryptographic Token Generation & Hashing Tests
# -----------------------------------------------------------------------------
def test_token_generation_and_hashing():
    t1 = generate_access_token()
    t2 = generate_access_token()
    assert t1 != t2, "Tokens must be unique"
    assert len(t1) >= 40, "Token must provide at least 256 bits of URL-safe entropy"

    h1 = hash_access_token(t1)
    h2 = hash_access_token(t1)
    h3 = hash_access_token(t2)
    assert h1 == h2, "Hashing must be deterministic"
    assert h1 != h3, "Different tokens must produce different hashes"
    assert len(h1) == 64, "SHA-256 hash must be 64 hexadecimal characters"


# -----------------------------------------------------------------------------
# 2. Upload Endpoint (Accessible Without Token)
# -----------------------------------------------------------------------------
def test_upload_without_token_issues_access_token():
    docx_bytes = create_sample_docx()
    files = {"file": ("test_resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 200, f"Upload failed: {res.text}"
    data = res.json()
    assert "id" in data
    assert "access_token" in data
    assert data["access_token"] is not None
    assert len(data["access_token"]) >= 40
    assert data["parsing_status"] == "PARSED"


# -----------------------------------------------------------------------------
# 3. Access Verification & Authorization Denial Tests
# -----------------------------------------------------------------------------
def test_valid_token_permits_access():
    docx_bytes = create_sample_docx()
    files = {"file": ("valid_test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    upload_data = upload_res.json()
    resume_id = upload_data["id"]
    token = upload_data["access_token"]

    # Access metadata with valid token
    headers = {"X-Resume-Token": token}
    meta_res = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert meta_res.status_code == 200, f"Expected 200 with valid token, got {meta_res.status_code}"
    assert meta_res.json()["id"] == resume_id


def test_missing_token_denied_with_404():
    docx_bytes = create_sample_docx()
    files = {"file": ("no_token.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    resume_id = upload_res.json()["id"]

    # Access without X-Resume-Token header
    res = client.get(f"/api/resumes/{resume_id}")
    assert res.status_code == 404, f"Expected 404 on missing token, got {res.status_code}"
    assert f"Resume with ID {resume_id} not found." in res.json()["detail"]


def test_invalid_token_denied_with_404():
    docx_bytes = create_sample_docx()
    files = {"file": ("bad_token.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    resume_id = upload_res.json()["id"]

    # Access with tampered/incorrect token
    headers = {"X-Resume-Token": "invalid_wrong_token_1234567890abcdef"}
    res = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert res.status_code == 404, f"Expected 404 on invalid token, got {res.status_code}"


def test_cross_visitor_isolation():
    """Visitor A's token cannot access Visitor B's resume."""
    docx_bytes = create_sample_docx()
    # Visitor A
    files_a = {"file": ("visitor_a.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res_a = client.post("/api/resumes/upload", files=files_a).json()
    id_a = res_a["id"]
    token_a = res_a["access_token"]

    # Visitor B
    files_b = {"file": ("visitor_b.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res_b = client.post("/api/resumes/upload", files=files_b).json()
    id_b = res_b["id"]
    token_b = res_b["access_token"]

    assert id_a != id_b
    assert token_a != token_b

    # Visitor A tries to access Visitor B's resume with Token A
    probe_res = client.get(f"/api/resumes/{id_b}", headers={"X-Resume-Token": token_a})
    assert probe_res.status_code == 404, "Visitor A must NOT be able to access Visitor B's resume"

    # Visitor B tries to access Visitor A's resume with Token B
    probe_res2 = client.get(f"/api/resumes/{id_a}", headers={"X-Resume-Token": token_b})
    assert probe_res2.status_code == 404, "Visitor B must NOT be able to access Visitor A's resume"


# -----------------------------------------------------------------------------
# 4. Coverage Across All Resume-Specific Endpoints
# -----------------------------------------------------------------------------
def test_all_endpoints_require_token():
    docx_bytes = create_sample_docx()
    files = {"file": ("endpoint_coverage.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    resume_id = upload_res.json()["id"]
    valid_token = upload_res.json()["access_token"]

    # List of endpoints to verify denial on missing token
    endpoints = [
        ("GET", f"/api/resumes/{resume_id}"),
        ("POST", f"/api/resumes/{resume_id}/analyze"),
        ("GET", f"/api/resumes/{resume_id}/analysis"),
        ("GET", f"/api/resumes/{resume_id}/matches"),
        ("GET", f"/api/resumes/{resume_id}/matches/1"),
        ("POST", f"/api/resumes/{resume_id}/skill-gaps/analyze"),
        ("GET", f"/api/resumes/{resume_id}/skill-gaps"),
        ("GET", f"/api/resumes/{resume_id}/skill-gaps/1"),
        ("POST", f"/api/resumes/{resume_id}/career-recommendations/analyze"),
        ("GET", f"/api/resumes/{resume_id}/career-recommendations"),
        ("GET", f"/api/resumes/{resume_id}/career-recommendations/1"),
        ("POST", f"/api/resumes/{resume_id}/resource-recommendations/analyze"),
        ("GET", f"/api/resumes/{resume_id}/learning-resources"),
        ("GET", f"/api/resumes/{resume_id}/learning-resources/1"),
        ("GET", f"/api/resumes/{resume_id}/certifications"),
        ("GET", f"/api/resumes/{resume_id}/certifications/1"),
        ("GET", f"/api/resumes/{resume_id}/resource-recommendations"),
        ("GET", f"/api/resumes/{resume_id}/resource-recommendations/1"),
        ("DELETE", f"/api/resumes/{resume_id}"),
    ]

    for method, path in endpoints:
        # Request WITHOUT token must be rejected with 404
        if method == "GET":
            r_no_token = client.get(path)
        elif method == "POST":
            r_no_token = client.post(path)
        elif method == "DELETE":
            r_no_token = client.delete(path)
        assert r_no_token.status_code == 404, f"{method} {path} without token returned {r_no_token.status_code}, expected 404"

        # Request WITH invalid token must also be rejected with 404
        bad_hdr = {"X-Resume-Token": "bad_token"}
        if method == "GET":
            r_bad_token = client.get(path, headers=bad_hdr)
        elif method == "POST":
            r_bad_token = client.post(path, headers=bad_hdr)
        elif method == "DELETE":
            r_bad_token = client.delete(path, headers=bad_hdr)
        assert r_bad_token.status_code == 404, f"{method} {path} with bad token returned {r_bad_token.status_code}, expected 404"


# -----------------------------------------------------------------------------
# 5. Secure Deletion & Catalog Data Preservation
# -----------------------------------------------------------------------------
def test_secure_deletion_and_catalog_preservation():
    docx_bytes = create_sample_docx()
    files = {"file": ("delete_test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    resume_id = upload_res.json()["id"]
    token = upload_res.json()["access_token"]
    headers = {"X-Resume-Token": token}

    # Analyze first to populate child tables
    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200

    # Verify resume and child entries exist in DB
    with TestingSessionLocal() as db:
        assert db.query(Resume).filter(Resume.id == resume_id).first() is not None
        initial_skills_count = db.query(Skill).count()
        initial_roles_count = db.query(JobRole).count()

    # Call DELETE with valid token
    del_res = client.delete(f"/api/resumes/{resume_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify resume is completely gone
    with TestingSessionLocal() as db:
        assert db.query(Resume).filter(Resume.id == resume_id).first() is None
        # Verify catalog tables remain untouched
        assert db.query(Skill).count() == initial_skills_count, "Catalog skills must remain untouched"
        assert db.query(JobRole).count() == initial_roles_count, "Catalog job roles must remain untouched"

    # Subsequent GET with the old token returns 404
    get_after = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert get_after.status_code == 404


# -----------------------------------------------------------------------------
# 6. Upload Size & File Format Validation Tests
# -----------------------------------------------------------------------------
def test_file_size_limit_rejection():
    # 5 MB + 100 KB file (oversized)
    oversized_content = b"%PDF-1.4 " + (b"0" * (5 * 1024 * 1024 + 100 * 1024))
    files = {"file": ("too_large.pdf", oversized_content, "application/pdf")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 400
    assert "File size exceeds the 5 MB limit" in res.json()["detail"]


def test_file_size_under_limit_accepted():
    # Under 5 MB valid DOCX
    docx_bytes = create_sample_docx()
    assert len(docx_bytes) < 5 * 1024 * 1024
    files = {"file": ("under_5mb.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 200


def test_unsupported_format_rejected():
    files = {"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-msdownload")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_magic_signature_mismatch_rejected():
    # .pdf extension with non-PDF content
    files = {"file": ("fake.pdf", b"This is plain text pretending to be PDF", "application/pdf")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 400
    assert "File signature mismatch" in res.json()["detail"]


def test_malformed_pdf_handled_gracefully():
    # Valid PDF magic header bytes but corrupt/truncated body
    corrupt_pdf_content = b"%PDF-1.4\n%%EOF\nThis is completely corrupt garbage body << >>"
    files = {"file": ("corrupt.pdf", corrupt_pdf_content, "application/pdf")}
    res = client.post("/api/resumes/upload", files=files)
    
    # Endpoint must handle it gracefully (200 OK with FAILED parsing status, or 400 Bad Request)
    assert res.status_code in (200, 400), f"Expected 200 or 400, got {res.status_code}"
    
    if res.status_code == 200:
        data = res.json()
        assert data["parsing_status"] == "FAILED"
        assert "access_token" in data
        assert data["character_count"] == 0
        assert "Malformed" in data["message"] or "Unable to parse" in data["message"] or "corrupted" in data["message"].lower() or "No readable text" in data["message"]


# -----------------------------------------------------------------------------
# 7. End-to-End Pipeline With Token Authorization
# -----------------------------------------------------------------------------
def test_full_pipeline_with_token():
    docx_bytes = create_sample_docx()
    files = {"file": ("e2e_pipeline.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = client.post("/api/resumes/upload", files=files)
    assert upload_res.status_code == 200
    resume_id = upload_res.json()["id"]
    token = upload_res.json()["access_token"]
    headers = {"X-Resume-Token": token}

    # Analyze
    analyze_res = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200
    analysis = analyze_res.json()
    assert "candidate" in analysis
    assert "skills" in analysis

    # Matches
    match_res = client.get(f"/api/resumes/{resume_id}/matches", headers=headers)
    assert match_res.status_code == 200
    assert "matches" in match_res.json()

    # Skill Gaps
    gap_post = client.post(f"/api/resumes/{resume_id}/skill-gaps/analyze", headers=headers)
    assert gap_post.status_code == 200
    gap_get = client.get(f"/api/resumes/{resume_id}/skill-gaps", headers=headers)
    assert gap_get.status_code == 200

    # Career Recommendations
    rec_post = client.post(f"/api/resumes/{resume_id}/career-recommendations/analyze", headers=headers)
    assert rec_post.status_code == 200
    rec_get = client.get(f"/api/resumes/{resume_id}/career-recommendations", headers=headers)
    assert rec_get.status_code == 200

    # Resource Recommendations
    res_post = client.post(f"/api/resumes/{resume_id}/resource-recommendations/analyze", headers=headers)
    assert res_post.status_code == 200
    res_get = client.get(f"/api/resumes/{resume_id}/resource-recommendations", headers=headers)
    assert res_get.status_code == 200

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    setup_module()
    print("setup_module completed!")
    tests = [
        test_token_generation_and_hashing,
        test_upload_without_token_issues_access_token,
        test_valid_token_permits_access,
        test_missing_token_denied_with_404,
        test_invalid_token_denied_with_404,
        test_cross_visitor_isolation,
        test_all_endpoints_require_token,
        test_secure_deletion_and_catalog_preservation,
        test_file_size_limit_rejection,
        test_file_size_under_limit_accepted,
        test_unsupported_format_rejected,
        test_magic_signature_mismatch_rejected,
        test_malformed_pdf_handled_gracefully,
        test_full_pipeline_with_token,
    ]

    passed = 0
    failed = 0
    print("=" * 70)
    print("RUNNING PHASE 1 SECURITY TEST SUITE (IN-MEMORY SQLITE ISOLATION)")
    print("=" * 70)
    from backend.services.rate_limiter import reset_rate_limiter
    for t in tests:
        reset_rate_limiter()
        name = t.__name__
        print(f"Running {name}...")
        try:
            t()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    teardown_module()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)
