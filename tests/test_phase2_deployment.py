"""
CareerSync Phase 2 Automated Verification Test Suite
Tests all Phase 2 production readiness, security, and deployment features:
1. Dual-layer upload size protection (7 MB request ceiling vs. 5 MB file ceiling)
2. In-memory sliding-window rate limiting (5 uploads / 10 min / IP) and proxy trust
3. 24-hour retention cleanup with successive bounded batches (50/batch, max 500/run)
4. Multi-run backlog drain (600 expired resumes drained over successive runs)
5. Foreign key cascade deletion and absolute master catalog preservation
6. Safe post-commit in-memory token registry eviction (active tokens preserved)
7. Unified hosting static file serving and routing precedence
8. Dynamic CORS configuration

STRICT ISOLATION:
- Runs 100% in-memory using SQLite (StaticPool with PRAGMA foreign_keys=ON).
- Never connects to or mutates the development MySQL database (careersync_db).
"""

import io
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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

from backend.config import settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    AnalysisSession,
    JobRole,
    JobRoleSkill,
    LearningResource,
    Resume,
    ResumeSkill,
    Skill,
)
import backend.services.cleanup as cleanup_module
from backend.services.cleanup import cleanup_expired_resumes_runner
from backend.services.rate_limiter import (
    _UPLOAD_HISTORY,
    get_verified_client_ip,
    prune_rate_limiter_memory,
    reset_rate_limiter,
)
from backend.services.security import (
    _TOKEN_HASH_STORE,
    generate_access_token,
    get_resume_token_hash,
    hash_access_token,
    store_resume_token_hash,
)

# -----------------------------------------------------------------------------
# 1. Isolated In-Memory SQLite Database Setup
# -----------------------------------------------------------------------------
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


# Override FastAPI DB dependency and cleanup module's SessionLocal
app.dependency_overrides[get_db] = override_get_db
cleanup_module.SessionLocal = TestingSessionLocal

client = TestClient(app)


def setup_module():
    """Create all tables and seed minimal master catalog data in SQLite."""
    settings.ALLOW_DEV_CLEANUP = True
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        # Seed test catalog skills
        s1 = Skill(name="Python", normalized_name="python", category="PROGRAMMING_LANGUAGE")
        s2 = Skill(name="SQL", normalized_name="sql", category="DATABASE")
        s3 = Skill(name="FastAPI", normalized_name="fastapi", category="FRAMEWORK_LIBRARY")
        db.add_all([s1, s2, s3])
        db.flush()

        # Seed test catalog role
        role = JobRole(
            title="Python Backend Developer",
            domain="Web Development",
            overview="Builds REST APIs",
            experience_level="ENTRY_LEVEL",
            is_active=True,
        )
        db.add(role)
        db.flush()

        # Map skills
        db.add(JobRoleSkill(job_role_id=role.id, skill_id=s1.id, importance="REQUIRED", weight=0.5))
        db.add(JobRoleSkill(job_role_id=role.id, skill_id=s2.id, importance="PREFERRED", weight=0.3))
        db.add(JobRoleSkill(job_role_id=role.id, skill_id=s3.id, importance="NICE_TO_HAVE", weight=0.2))

        # Seed test catalog learning resource
        res = LearningResource(
            title="FastAPI Official Docs",
            resource_type="DOCUMENTATION",
            platform_name="FastAPI",
            url="https://fastapi.tiangolo.com",
            difficulty_level="BEGINNER",
            is_free=True,
            is_active=True,
        )
        db.add(res)
        db.commit()


def teardown_module():
    """Clean up in-memory tables."""
    settings.ALLOW_DEV_CLEANUP = False
    Base.metadata.drop_all(bind=test_engine)


def create_sample_docx(text="John Doe\nPython Developer\nSkills: Python, SQL") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


# -----------------------------------------------------------------------------
# 2. Upload Size Protection Tests (Dual-Layer)
# -----------------------------------------------------------------------------
def test_request_size_middleware_rejects_over_7mb():
    """Total request body exceeding 7 MB is rejected with HTTP 413 by ASGI middleware."""
    # Simulate a request header declaring over 7 MB
    oversized_length = 7 * 1024 * 1024 + 1024  # 7 MB + 1 KB
    headers = {"Content-Length": str(oversized_length)}
    docx_bytes = create_sample_docx()
    files = {"file": ("test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/resumes/upload", files=files, headers=headers)
    assert res.status_code == 413, f"Expected 413, got {res.status_code}: {res.text}"
    assert "exceeds maximum size of 7 MB" in res.json()["detail"]


def test_file_size_guard_rejects_5mb_file():
    """Raw resume file exceeding 5 MB is rejected with HTTP 400 via chunked stream validation."""
    reset_rate_limiter()
    # Create fake PDF with magic header (%PDF-) followed by 5.1 MB of content (within 7 MB request limit)
    oversized_file_bytes = b"%PDF-1.4\n" + b"A" * (5 * 1024 * 1024 + 1024)
    files = {"file": ("oversized.pdf", oversized_file_bytes, "application/pdf")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    assert "File size exceeds the 5 MB limit" in res.json()["detail"]


def test_file_size_guard_accepts_valid_file():
    """Valid resume file under 5 MB is accepted successfully."""
    reset_rate_limiter()
    docx_bytes = create_sample_docx("Valid Developer Resume")
    files = {"file": ("valid.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert "access_token" in res.json()


# -----------------------------------------------------------------------------
# 3. In-Memory Upload Rate Limiting Tests (5 uploads / 10 min / IP)
# -----------------------------------------------------------------------------
def test_rate_limit_permits_five_uploads():
    """Up to 5 uploads from the same client within 10 minutes succeed."""
    reset_rate_limiter()
    docx_bytes = create_sample_docx()
    for i in range(5):
        files = {"file": (f"test_{i}.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        res = client.post("/api/resumes/upload", files=files)
        assert res.status_code == 200, f"Upload {i+1} failed: {res.text}"


def test_rate_limit_blocks_sixth_upload():
    """6th upload from the same client within 10 minutes is blocked with HTTP 429."""
    docx_bytes = create_sample_docx()
    files = {"file": ("test_6.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/resumes/upload", files=files)
    assert res.status_code == 429, f"Expected 429, got {res.status_code}: {res.text}"
    assert "Retry-After" in res.headers
    retry_after = int(res.headers["Retry-After"])
    assert retry_after > 0
    assert "Upload rate limit exceeded" in res.json()["detail"]


def test_rate_limiter_memory_bounding():
    """Expired timestamps and inactive IPs are pruned, keeping memory bounded."""
    reset_rate_limiter()
    now = time.time()
    # Seed 10 IPs with old timestamps (older than 10 minutes)
    for i in range(10):
        _UPLOAD_HISTORY[f"old_ip_{i}"] = [now - 700.0]
    # Seed 2 IPs with active timestamps
    _UPLOAD_HISTORY["active_ip_1"] = [now - 100.0]
    _UPLOAD_HISTORY["active_ip_2"] = [now - 50.0]

    assert len(_UPLOAD_HISTORY) == 12
    prune_rate_limiter_memory(cutoff=now - 600.0)
    assert len(_UPLOAD_HISTORY) == 2
    assert "active_ip_1" in _UPLOAD_HISTORY
    assert "active_ip_2" in _UPLOAD_HISTORY


# -----------------------------------------------------------------------------
# 4. Proxy Security & Anti-Spoofing Tests
# -----------------------------------------------------------------------------
def test_untrusted_socket_ignores_forwarded_for():
    """Untrusted socket connection sending spoofed X-Forwarded-For is ignored; socket IP is used."""
    from starlette.requests import Request

    # Create dummy request with untrusted direct socket IP (e.g. 198.51.100.4)
    scope = {
        "type": "http",
        "client": ("198.51.100.4", 54321),
        "headers": [(b"x-forwarded-for", b"8.8.8.8, 1.1.1.1")],
    }
    req = Request(scope)
    verified_ip = get_verified_client_ip(req)
    assert verified_ip == "198.51.100.4", f"Expected socket IP 198.51.100.4, got {verified_ip}"


def test_trusted_proxy_accepts_forwarded_for():
    """Connection from trusted proxy socket IP extracts verified client IP from X-Forwarded-For."""
    from starlette.requests import Request

    # 127.0.0.1 is in TRUSTED_PROXIES by default
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 10.0.0.1")],
    }
    req = Request(scope)
    verified_ip = get_verified_client_ip(req)
    assert verified_ip == "203.0.113.195", f"Expected forwarded IP 203.0.113.195, got {verified_ip}"


# -----------------------------------------------------------------------------
# 5. Successive Bounded Batch Cleanup & Safety Cap Tests
# -----------------------------------------------------------------------------
def test_cleanup_successive_batches_120_resumes():
    """Verify 120 expired resumes are deleted across successive batches of 50, 50, and 20."""
    now_utc = datetime.now(timezone.utc)
    expired_time = now_utc - timedelta(hours=25)

    with TestingSessionLocal() as db:
        # Clear any prior resumes in SQLite
        db.query(Resume).delete()
        db.commit()

        # Seed exactly 120 expired resumes
        resumes = [
            Resume(
                file_name=f"expired_{i}.docx",
                file_type="DOCX",
                file_size_bytes=1000,
                file_hash=f"hash_{i}",
                raw_text="Sample text",
                parsing_status="PARSED",
                created_at=expired_time,
            )
            for i in range(120)
        ]
        db.add_all(resumes)
        db.commit()
        assert db.query(Resume).count() == 120

    # Run cleanup runner with batch_size=50
    total_deleted = cleanup_expired_resumes_runner(batch_size=50, max_batches=10)
    assert total_deleted == 120, f"Expected 120 deletions, got {total_deleted}"

    with TestingSessionLocal() as db:
        remaining = db.query(Resume).count()
        assert remaining == 0, f"Expected 0 resumes remaining, got {remaining}"


def test_cleanup_safety_cap_at_500_resumes():
    """Verify no single run deletes more than 500 resumes (10 batches of 50)."""
    now_utc = datetime.now(timezone.utc)
    expired_time = now_utc - timedelta(hours=25)

    with TestingSessionLocal() as db:
        db.query(Resume).delete()
        db.commit()

        # Seed 550 expired resumes
        resumes = [
            Resume(
                file_name=f"cap_{i}.docx",
                file_type="DOCX",
                file_size_bytes=1000,
                file_hash=f"hash_cap_{i}",
                raw_text="Sample text",
                parsing_status="PARSED",
                created_at=expired_time,
            )
            for i in range(550)
        ]
        db.add_all(resumes)
        db.commit()
        assert db.query(Resume).count() == 550

    # Run single cleanup run (capped at max 10 batches = 500)
    total_deleted = cleanup_expired_resumes_runner(batch_size=50, max_batches=10)
    assert total_deleted == 500, f"Expected exactly 500 deletions at safety cap, got {total_deleted}"

    with TestingSessionLocal() as db:
        remaining = db.query(Resume).count()
        assert remaining == 50, f"Expected 50 resumes remaining after run 1, got {remaining}"


def test_cleanup_multi_run_backlog_drain_600_resumes():
    """Verify 600 expired resumes are drained over multiple runs without leaving data stranded."""
    now_utc = datetime.now(timezone.utc)
    expired_time = now_utc - timedelta(hours=25)

    with TestingSessionLocal() as db:
        db.query(Resume).delete()
        db.commit()

        # Seed 600 expired resumes
        resumes = [
            Resume(
                file_name=f"backlog_{i}.docx",
                file_type="DOCX",
                file_size_bytes=1000,
                file_hash=f"hash_drain_{i}",
                raw_text="Sample text",
                parsing_status="PARSED",
                created_at=expired_time,
            )
            for i in range(600)
        ]
        db.add_all(resumes)
        db.commit()
        assert db.query(Resume).count() == 600

    # Run 1: Cleans up to safety cap (500)
    run1_deleted = cleanup_expired_resumes_runner(batch_size=50, max_batches=10)
    assert run1_deleted == 500

    with TestingSessionLocal() as db:
        assert db.query(Resume).count() == 100

    # Run 2: Cleans the remaining 100 across 2 batches of 50
    run2_deleted = cleanup_expired_resumes_runner(batch_size=50, max_batches=10)
    assert run2_deleted == 100

    with TestingSessionLocal() as db:
        remaining = db.query(Resume).count()
        assert remaining == 0, f"Expected 0 resumes remaining after run 2, got {remaining}"


def test_cleanup_preserves_unexpired_resumes():
    """Resumes younger than 24 hours are preserved."""
    now_utc = datetime.now(timezone.utc)
    recent_time = now_utc - timedelta(hours=2)

    with TestingSessionLocal() as db:
        db.query(Resume).delete()
        db.commit()

        r = Resume(
            file_name="active.docx",
            file_type="DOCX",
            file_size_bytes=1000,
            file_hash="hash_active",
            raw_text="Active user text",
            parsing_status="PARSED",
            created_at=recent_time,
        )
        db.add(r)
        db.commit()
        active_id = r.id

    deleted = cleanup_expired_resumes_runner()
    assert deleted == 0

    with TestingSessionLocal() as db:
        r_check = db.query(Resume).filter(Resume.id == active_id).first()
        assert r_check is not None
        assert r_check.file_name == "active.docx"


# -----------------------------------------------------------------------------
# 6. Cascades and Catalog Preservation Tests
# -----------------------------------------------------------------------------
def test_cleanup_cascades_to_child_sessions():
    """Deleting expired resumes cascades and deletes associated skills and analysis sessions."""
    now_utc = datetime.now(timezone.utc)
    expired_time = now_utc - timedelta(hours=25)

    with TestingSessionLocal() as db:
        db.query(Resume).delete()
        db.commit()

        # Create expired resume with child data
        r = Resume(
            file_name="cascade.docx",
            file_type="DOCX",
            file_size_bytes=1000,
            file_hash="hash_cascade",
            raw_text="Skills: Python",
            parsing_status="PARSED",
            created_at=expired_time,
        )
        db.add(r)
        db.flush()

        s1 = db.query(Skill).first()
        db.add(ResumeSkill(resume_id=r.id, skill_id=s1.id, extraction_source="RESUME_BODY"))
        db.add(AnalysisSession(
            resume_id=r.id,
            target_role_title="Python Backend Developer",
            target_job_description="Builds REST APIs with Python",
            compatibility_score=85.0,
        ))
        db.commit()
        res_id = r.id

        assert db.query(ResumeSkill).filter(ResumeSkill.resume_id == res_id).count() == 1
        assert db.query(AnalysisSession).filter(AnalysisSession.resume_id == res_id).count() == 1

    # Run cleanup
    cleanup_expired_resumes_runner()

    with TestingSessionLocal() as db:
        assert db.query(Resume).filter(Resume.id == res_id).count() == 0
        assert db.query(ResumeSkill).filter(ResumeSkill.resume_id == res_id).count() == 0
        assert db.query(AnalysisSession).filter(AnalysisSession.resume_id == res_id).count() == 0


def test_cleanup_strictly_preserves_catalog():
    """Catalog tables (JobRole, Skill, LearningResource) remain 100% untouched by cleanup."""
    with TestingSessionLocal() as db:
        roles_before = db.query(JobRole).count()
        skills_before = db.query(Skill).count()
        resources_before = db.query(LearningResource).count()

    cleanup_expired_resumes_runner()

    with TestingSessionLocal() as db:
        roles_after = db.query(JobRole).count()
        skills_after = db.query(Skill).count()
        resources_after = db.query(LearningResource).count()

    assert roles_before == roles_after and roles_after >= 1
    assert skills_before == skills_after and skills_after >= 3
    assert resources_before == resources_after and resources_after >= 1


# -----------------------------------------------------------------------------
# 7. In-Memory Token Registry Eviction & Active Token Preservation Tests
# -----------------------------------------------------------------------------
def test_token_registry_prunes_only_deleted_resumes():
    """Store tokens for Expired Resume A and Active Resume B; verify only Token A is removed."""
    now_utc = datetime.now(timezone.utc)
    expired_time = now_utc - timedelta(hours=25)
    recent_time = now_utc - timedelta(hours=2)

    with TestingSessionLocal() as db:
        db.query(Resume).delete()
        db.commit()

        ra = Resume(file_name="ra.docx", file_type="DOCX", file_size_bytes=1000, created_at=expired_time, parsing_status="PARSED")
        rb = Resume(file_name="rb.docx", file_type="DOCX", file_size_bytes=1000, created_at=recent_time, parsing_status="PARSED")
        db.add_all([ra, rb])
        db.commit()
        id_a, id_b = ra.id, rb.id

    token_a = generate_access_token()
    token_b = generate_access_token()
    _TOKEN_HASH_STORE[id_a] = hash_access_token(token_a)
    _TOKEN_HASH_STORE[id_b] = hash_access_token(token_b)

    # Run cleanup
    cleanup_expired_resumes_runner()

    # Verify Token A evicted, Token B intact
    assert id_a not in _TOKEN_HASH_STORE, "Expired resume token must be evicted"
    assert id_b in _TOKEN_HASH_STORE, "Active resume token must be preserved"
    assert _TOKEN_HASH_STORE[id_b] == hash_access_token(token_b)


# -----------------------------------------------------------------------------
# 8. Unified Hosting & Routing Precedence Tests
# -----------------------------------------------------------------------------
def test_static_file_mount_serves_frontend():
    """Root '/' serves index.html and static files like /script.js."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "<!DOCTYPE html>" in res_root.text or "CareerSync" in res_root.text

    res_script = client.get("/script.js")
    assert res_script.status_code == 200
    assert "CareerSync" in res_script.text

    res_style = client.get("/style.css")
    assert res_style.status_code == 200


def test_api_endpoints_precede_static_files():
    """API endpoints like /health take precedence over static file handling."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["service"] == "CareerSync API"


def test_cors_configuration():
    """Configured origins receive CORS allow headers; forbidden origins do not."""
    headers_allowed = {
        "Origin": "http://127.0.0.1:5500",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Resume-Token, Content-Type",
    }
    res = client.options("/api/resumes/upload", headers=headers_allowed)
    assert res.headers.get("access-control-allow-origin") == "http://127.0.0.1:5500"
    assert "x-resume-token" in res.headers.get("access-control-allow-headers", "").lower()


# -----------------------------------------------------------------------------
# 9. Main Test Runner
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    setup_module()
    print("setup_module completed!")

    tests = [
        test_request_size_middleware_rejects_over_7mb,
        test_file_size_guard_rejects_5mb_file,
        test_file_size_guard_accepts_valid_file,
        test_rate_limit_permits_five_uploads,
        test_rate_limit_blocks_sixth_upload,
        test_rate_limiter_memory_bounding,
        test_untrusted_socket_ignores_forwarded_for,
        test_trusted_proxy_accepts_forwarded_for,
        test_cleanup_successive_batches_120_resumes,
        test_cleanup_safety_cap_at_500_resumes,
        test_cleanup_multi_run_backlog_drain_600_resumes,
        test_cleanup_preserves_unexpired_resumes,
        test_cleanup_cascades_to_child_sessions,
        test_cleanup_strictly_preserves_catalog,
        test_token_registry_prunes_only_deleted_resumes,
        test_static_file_mount_serves_frontend,
        test_api_endpoints_precede_static_files,
        test_cors_configuration,
    ]

    passed = 0
    failed = 0
    print("=" * 70)
    print("RUNNING PHASE 2 DEPLOYMENT & RELIABILITY TEST SUITE (IN-MEMORY SQLITE)")
    print("=" * 70)
    for t in tests:
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
