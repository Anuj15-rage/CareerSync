"""
In-memory sliding-window upload rate limiter for CareerSync.
Tracks client upload timestamps over a rolling 10-minute window (default: 5 uploads per 10 minutes).
Strictly enforces trusted proxy verification before inspecting forwarded client-IP headers.
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import HTTPException, Request, status

from backend.config import settings

logger = logging.getLogger("careersync.rate_limiter")

# In-memory storage: client_ip -> list of POSIX timestamps
_UPLOAD_HISTORY: Dict[str, List[float]] = defaultdict(list)
_MAX_TRACKED_IPS = 10000


def get_verified_client_ip(request: Request) -> str:
    """
    Extract verified client IP.
    Trusts forwarded headers (X-Forwarded-For, X-Real-IP) ONLY if the immediate direct
    socket connection originates from an explicitly configured trusted proxy.
    """
    socket_ip = request.client.host if request.client else "127.0.0.1"
    normalized_socket_ip = socket_ip.strip().lower()

    # Check if immediate socket connection is in TRUSTED_PROXIES
    if normalized_socket_ip in settings.trusted_proxies_set:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Client IP is the leftmost IP added before the trusted proxy chain
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip
        real_ip = request.headers.get("X-Real-IP")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    # Untrusted direct connection or missing headers: strictly return direct socket_ip
    return socket_ip


def check_upload_rate_limit(request: Request) -> str:
    """
    FastAPI dependency enforcing upload rate limit per IP.
    Raises HTTP 429 Too Many Requests if limit is exceeded.
    """
    client_ip = get_verified_client_ip(request)
    now = time.time()
    window = float(settings.RATE_LIMIT_WINDOW_SECONDS)
    max_uploads = settings.RATE_LIMIT_UPLOADS
    cutoff = now - window

    # Clean expired entries for this IP
    timestamps = [t for t in _UPLOAD_HISTORY.get(client_ip, []) if t > cutoff]

    if len(timestamps) >= max_uploads:
        oldest_in_window = timestamps[0]
        retry_after = max(1, int(oldest_in_window + window - now))
        logger.warning(
            "Upload rate limit exceeded for client_ip=%s (count=%d, retry_after=%ds)",
            client_ip,
            len(timestamps),
            retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload rate limit exceeded. You may upload up to {max_uploads} resumes per {int(window // 60)} minutes.",
            headers={"Retry-After": str(retry_after)},
        )

    # Record current upload timestamp
    timestamps.append(now)
    _UPLOAD_HISTORY[client_ip] = timestamps

    # Memory bounding maintenance: prune inactive IPs if dictionary exceeds capacity
    if len(_UPLOAD_HISTORY) > _MAX_TRACKED_IPS:
        prune_rate_limiter_memory(cutoff)

    return client_ip


def prune_rate_limiter_memory(cutoff: Optional[float] = None) -> None:
    """
    Prune empty or completely expired IP entries from memory to maintain bounded size.
    """
    if cutoff is None:
        cutoff = time.time() - float(settings.RATE_LIMIT_WINDOW_SECONDS)

    stale_keys = [
        ip for ip, ts in _UPLOAD_HISTORY.items()
        if not ts or ts[-1] <= cutoff
    ]
    for ip in stale_keys:
        _UPLOAD_HISTORY.pop(ip, None)


def reset_rate_limiter() -> None:
    """
    Reset rate limiter store (used in test fixtures).
    """
    _UPLOAD_HISTORY.clear()
