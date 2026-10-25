"""
24-Hour Resume Lifecycle & Data Retention Cleanup Service for CareerSync.

Safely purges expired resumes and cascaded analysis records older than 24 hours.
Uses bounded successive batches (50 records per batch, max 10 batches = 500 records per run)
with independent database sessions and explicit transaction management.
Guarantees master catalog tables (skills, roles, resources) are never touched.
Evicts token hashes from memory post-commit only.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models.resume import Resume
from backend.services.security import remove_resume_token_hashes

logger = logging.getLogger("careersync.cleanup")

BATCH_SIZE = 50
MAX_BATCHES_PER_RUN = 10  # Max 500 deletions per run


def cleanup_expired_resumes_runner(
    batch_size: int = BATCH_SIZE,
    max_batches: int = MAX_BATCHES_PER_RUN,
    custom_cutoff: Optional[datetime] = None,
) -> int:
    """
    Core cleanup runner.
    Processes expired resumes across successive bounded batches.
    Each batch runs in an independent SessionLocal() with explicit commit and rollback.
    Returns total number of deleted resumes across this run.
    """
    # STRICT SAFEGUARD: Never delete records from development database 'careersync_db'
    if settings.DB_NAME == "careersync_db" and not getattr(settings, "ALLOW_DEV_CLEANUP", False):
        logger.info("Cleanup skipped: development database 'careersync_db' is protected from automatic deletion.")
        return 0

    total_deleted = 0
    cutoff = custom_cutoff or (datetime.now(timezone.utc) - timedelta(hours=settings.RESUME_EXPIRATION_HOURS))

    for batch_num in range(1, max_batches + 1):
        # 1. Independent Database Session per batch (never reuse request-scoped DB sessions)
        db: Session = SessionLocal()
        deleted_ids = []
        try:
            # 2. Query bounded batch of expired resume IDs
            expired_batch = (
                db.query(Resume.id)
                .filter(Resume.created_at < cutoff)
                .limit(batch_size)
                .all()
            )
            if not expired_batch:
                break  # No more expired records to delete

            target_ids = [r[0] for r in expired_batch]

            # 3. Explicit Transaction Handling
            # Deletion cascades at DB level to child tables (resume_skills, analysis_sessions, etc.)
            db.query(Resume).filter(Resume.id.in_(target_ids)).delete(synchronize_session=False)
            db.commit()

            deleted_ids = target_ids
            total_deleted += len(target_ids)
            logger.info("Cleanup batch %d: deleted %d expired resumes", batch_num, len(target_ids))

        except Exception as exc:
            db.rollback()  # Guaranteed rollback on error
            logger.error("Cleanup batch %d failed with error (rolled back): %s", batch_num, exc, exc_info=True)
            break  # Stop run on error; do not loop infinitely
        finally:
            db.close()  # Guaranteed session disposal; prevents connection leaks

        # 4. Safe In-Memory Token Eviction (Post-Commit ONLY)
        if deleted_ids:
            remove_resume_token_hashes(deleted_ids)

        # If batch had fewer records than batch_size, all expired resumes have been drained
        if len(target_ids) < batch_size:
            break

    return total_deleted


def trigger_lazy_cleanup() -> None:
    """
    Safe wrapper invoked by FastAPI BackgroundTasks on upload activity.
    Catches any unexpected top-level exceptions so upload background tasks never fail quietly.
    """
    try:
        deleted = cleanup_expired_resumes_runner()
        if deleted > 0:
            logger.info("Upload-triggered lazy cleanup finished: purged %d expired resumes", deleted)
    except Exception as exc:
        logger.error("Unexpected error in upload-triggered lazy cleanup: %s", exc, exc_info=True)


async def periodic_cleanup_loop(interval_minutes: Optional[int] = None) -> None:
    """
    Periodic background loop running inside the FastAPI lifespan while active.
    Sleeps interval_minutes between runs and safely handles cancellations on shutdown.
    """
    interval_secs = (interval_minutes or settings.CLEANUP_INTERVAL_MINUTES) * 60
    logger.info("Periodic cleanup worker started with interval of %d minutes.", interval_secs // 60)
    try:
        while True:
            await asyncio.sleep(interval_secs)
            try:
                deleted = cleanup_expired_resumes_runner()
                if deleted > 0:
                    logger.info("Periodic cleanup cycle completed: purged %d expired resumes", deleted)
            except Exception as exc:
                logger.error("Error during periodic cleanup cycle: %s", exc, exc_info=True)
    except asyncio.CancelledError:
        logger.info("Periodic cleanup worker stopped cleanly.")
