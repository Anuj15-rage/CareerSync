"""
Security and Access Token Management for CareerSync (Phase 1)

Provides cryptographically secure token generation, SHA-256 token hashing,
database/in-memory token persistence, and FastAPI authorization dependencies.
"""

import hashlib
import logging
import secrets
from typing import Dict, Iterable, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.resume import Resume

logger = logging.getLogger(__name__)

# In-memory token hash store: resume_id -> sha256_hash
# Acts as fast lookup and ensures zero-breaking-change fallback when the DB
# column has not yet been migrated in development.
_TOKEN_HASH_STORE: Dict[int, str] = {}

# Cached flag for whether the physical table has access_token_hash column
_HAS_TOKEN_COLUMN: Optional[bool] = None


def generate_access_token() -> str:
    """
    Generate a cryptographically secure URL-safe random token.
    32 bytes provides 256 bits of entropy.
    """
    return secrets.token_urlsafe(32)


def hash_access_token(token: str) -> str:
    """
    Compute deterministic SHA-256 hexadecimal hash of the access token.
    """
    if not token:
        return ""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def has_token_column(bind) -> bool:
    """
    Inspect the database schema to check if 'access_token_hash' column exists
    in the 'resumes' table. Caches the result to avoid repeated reflection.
    """
    global _HAS_TOKEN_COLUMN
    if _HAS_TOKEN_COLUMN is not None:
        return _HAS_TOKEN_COLUMN

    try:
        inspector = inspect(bind)
        cols = [c["name"] for c in inspector.get_columns("resumes")]
        _HAS_TOKEN_COLUMN = "access_token_hash" in cols
    except Exception as e:
        logger.warning("Could not inspect table columns for access_token_hash: %s", e)
        _HAS_TOKEN_COLUMN = False

    return _HAS_TOKEN_COLUMN


def store_resume_token_hash(
    resume_id: int,
    token_hash: str,
    db: Session,
) -> None:
    """
    Store the token hash for the specified resume.
    Always records in-memory; also persists to MySQL if the column is present.
    """
    _TOKEN_HASH_STORE[resume_id] = token_hash

    # Persist to database column if physically present
    if has_token_column(db.get_bind()):
        try:
            db.execute(
                text("UPDATE resumes SET access_token_hash = :thash WHERE id = :rid"),
                {"thash": token_hash, "rid": resume_id},
            )
            db.commit()
            logger.debug("Persisted access_token_hash to DB for resume %s", resume_id)
        except Exception as e:
            logger.warning(
                "Failed to update access_token_hash in DB for resume %s: %s",
                resume_id,
                e,
            )


def get_resume_token_hash(resume_id: int, db: Session) -> Optional[str]:
    """
    Retrieve the expected SHA-256 token hash for a given resume_id.
    Checks in-memory store first, then queries the database column if available.
    """
    if resume_id in _TOKEN_HASH_STORE:
        return _TOKEN_HASH_STORE[resume_id]

    if has_token_column(db.get_bind()):
        try:
            row = db.execute(
                text("SELECT access_token_hash FROM resumes WHERE id = :rid"),
                {"rid": resume_id},
            ).fetchone()
            if row and row[0]:
                _TOKEN_HASH_STORE[resume_id] = row[0]
                return row[0]
        except Exception as e:
            logger.warning(
                "Failed to read access_token_hash from DB for resume %s: %s",
                resume_id,
                e,
            )

    return None


def remove_resume_token_hash(resume_id: int) -> None:
    """
    Clear the token hash from memory when a resume is deleted.
    """
    _TOKEN_HASH_STORE.pop(resume_id, None)


def remove_resume_token_hashes(resume_ids: Iterable[int]) -> None:
    """
    Clear multiple token hashes from memory post-commit when resumes are deleted in batch.
    """
    for rid in resume_ids:
        _TOKEN_HASH_STORE.pop(rid, None)


def verify_resume_access(
    resume_id: int,
    x_resume_token: Optional[str] = Header(None, alias="X-Resume-Token"),
    db: Session = Depends(get_db),
) -> Resume:
    """
    FastAPI dependency that enforces token-based authorization on resume-specific routes.

    Security rules:
    - If X-Resume-Token header is missing: returns uniform 404 Not Found.
    - If token hash does not match expected hash: returns uniform 404 Not Found.
    - If resume does not exist in DB: returns uniform 404 Not Found.
    - Returning 404 instead of 401/403 prevents attackers from probing valid resume IDs.
    - Returns the verified Resume object upon success.
    """
    not_found_exception = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Resume with ID {resume_id} not found.",
    )

    if not x_resume_token or not x_resume_token.strip():
        logger.warning(
            "Access denied: Missing X-Resume-Token for resume_id=%s", resume_id
        )
        raise not_found_exception

    provided_hash = hash_access_token(x_resume_token.strip())
    expected_hash = get_resume_token_hash(resume_id, db)

    if not expected_hash:
        logger.warning(
            "Access denied: No token hash recorded for resume_id=%s", resume_id
        )
        raise not_found_exception

    # Constant-time comparison
    if not secrets.compare_digest(provided_hash, expected_hash):
        logger.warning(
            "Access denied: Token mismatch for resume_id=%s", resume_id
        )
        raise not_found_exception

    # Verify resume actually exists in database
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        logger.warning(
            "Access denied: Resume record not found in DB for resume_id=%s", resume_id
        )
        raise not_found_exception

    return resume
