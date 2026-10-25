import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.api.resumes import router as resumes_router
from backend.config import BASE_DIR, settings
from backend.database import check_database_connection, get_db
from backend.models import (
    Certification,
    CertificationProvider,
    JobRole,
    LearningResource,
    Skill,
)
from backend.services.cleanup import cleanup_expired_resumes_runner, periodic_cleanup_loop

logger = logging.getLogger("careersync.main")


class RequestSizeLimitMiddleware:
    """
    ASGI middleware enforcing early request-layer size protection.
    Rejects requests exceeding MAX_REQUEST_SIZE_BYTES (default: 7 MB)
    via Content-Length header or streaming body accumulation before router processing.
    """

    def __init__(self, app: ASGIApp, max_request_size: int = 7 * 1024 * 1024):
        self.app = app
        self.max_request_size = max_request_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith("/api/resumes/upload"):
            headers = dict(scope.get("headers", []))
            content_length_str = headers.get(b"content-length")

            # 1. Early Content-Length Header Check
            if content_length_str:
                try:
                    content_length = int(content_length_str.decode("latin1"))
                    if content_length > self.max_request_size:
                        response = JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "detail": f"Request body exceeds maximum size of {self.max_request_size // (1024 * 1024)} MB."
                            },
                        )
                        await response(scope, receive, send)
                        return
                except (ValueError, UnicodeDecodeError):
                    pass

            # 2. Streaming Body Accumulation Guard (for missing or chunked Content-Length)
            bytes_received = 0

            async def wrapped_receive():
                nonlocal bytes_received
                message = await receive()
                if message["type"] == "http.request":
                    body = message.get("body", b"")
                    bytes_received += len(body)
                    if bytes_received > self.max_request_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Request body exceeds maximum size of {self.max_request_size // (1024 * 1024)} MB.",
                        )
                return message

            await self.app(scope, wrapped_receive, send)
            return

        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan manager.
    Runs one initial cleanup pass on startup, launches periodic background cleanup,
    and cleanly stops background workers on shutdown.
    """
    logger.info("CareerSync API starting up...")
    # Safe startup cleanup pass to drain any expired records after container sleep/downtime
    try:
        startup_deleted = cleanup_expired_resumes_runner()
        if startup_deleted > 0:
            logger.info("Startup cleanup cycle completed: purged %d expired resumes", startup_deleted)
    except Exception as exc:
        logger.warning("Startup cleanup pass encountered error (non-fatal): %s", exc)

    # Launch periodic background cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup_loop())

    yield

    # Clean shutdown
    logger.info("CareerSync API shutting down; stopping periodic cleanup worker...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="CareerSync API",
    description="Backend API for the Resume-Based Career and Resource Recommendation System",
    version="1.0.0",
    lifespan=lifespan,
)

# Request size limit middleware (enforces 7 MB request limit on uploads)
app.add_middleware(RequestSizeLimitMiddleware, max_request_size=settings.MAX_REQUEST_SIZE_BYTES)

# CORS configuration driven by settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True if settings.cors_origins_list != ["*"] else False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Resume-Token"],
)

# Include API routers first so API endpoints take routing precedence
app.include_router(resumes_router)


@app.get("/health")
def health_check():
    db_check = check_database_connection()
    return {
        "status": "healthy" if db_check["connected"] else "degraded",
        "service": "CareerSync API",
        "database": db_check,
    }


@app.get("/api/verification/seeded-data")
def verify_seeded_data(db: Session = Depends(get_db)):
    """
    Read-only verification endpoint that queries seeded catalog tables
    via SQLAlchemy ORM and returns counts and sample records.
    """
    skills_count = db.query(Skill).count()
    roles_count = db.query(JobRole).count()
    resources_count = db.query(LearningResource).count()
    certifications_count = db.query(Certification).count()
    providers_count = db.query(CertificationProvider).count()

    # Retrieve sample names (first 3) for confirmation
    sample_skills = [s.name for s in db.query(Skill).limit(3).all()]
    sample_roles = [r.title for r in db.query(JobRole).limit(3).all()]
    sample_resources = [res.title for res in db.query(LearningResource).limit(3).all()]
    sample_certs = [c.name for c in db.query(Certification).limit(3).all()]

    return {
        "status": "success",
        "counts": {
            "skills": skills_count,
            "job_roles": roles_count,
            "learning_resources": resources_count,
            "certifications": certifications_count,
            "certification_providers": providers_count,
        },
        "samples": {
            "skills": sample_skills,
            "job_roles": sample_roles,
            "learning_resources": sample_resources,
            "certifications": sample_certs,
        },
    }


# Mount static frontend files at root ('/') so FastAPI serves the unified application
# All API routes above take precedence; root '/' serves frontend/index.html
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
