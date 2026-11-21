"""
CareerSync Privacy & PII Sanitizer Service for Gemini LLM Integration.

Enforces zero-PII transmission boundaries:
1. Strips candidate name, email, phone, raw resume text, file contents, and access tokens.
2. Redacts in-text email addresses, phone numbers, profile URLs, cryptographic tokens, and candidate name references.
3. Enforces strict length caps and size limits to prevent oversized inputs and token exhaustion.
4. Returns strongly-typed SanitizedResumePayload compatible with Gemini structured prompts.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from backend.schemas.analysis import (
    SanitizedExperienceItem,
    SanitizedProjectItem,
    SanitizedResumePayload,
)

logger = logging.getLogger("careersync.services.privacy_sanitizer")

# -----------------------------------------------------------------------------
# PII Redaction Regex Patterns
# -----------------------------------------------------------------------------
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Matches formatted phone numbers (local, national, international) and 10-14 digit sequences
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{3}[-.\s]\d{4}\b|\b\+?\d{10,14}\b)"
)

# Matches URLs, web links, and profile handles
URL_PATTERN = re.compile(
    r"(?:\b(?:https?://|www\.)[^\s<>'\"{}|\\^`]+[^\s<>'\"{}|\\^`.,;:?!]|\b(?:linkedin\.com/in|github\.com)/[^\s<>'\"{}|\\^`]+[^\s<>'\"{}|\\^`.,;:?!])",
    re.IGNORECASE,
)

# Matches cryptographic hashes (MD5, SHA-256) and security tokens (32-64 hex chars)
TOKEN_PATTERN = re.compile(r"\b[a-fA-F0-9]{32,64}\b")

# Keys that must NEVER be passed directly in an unvetted dictionary payload
FORBIDDEN_PII_KEYS = {
    "candidate_name",
    "candidate_email",
    "candidate_phone",
    "raw_text",
    "file_name",
    "file_hash",
    "access_token",
    "access_token_hash",
}

# -----------------------------------------------------------------------------
# Sensible Size Ceiling Constants
# -----------------------------------------------------------------------------
MAX_SINGLE_FIELD_CHARS = 5000       # Maximum single input string before hard rejection
MAX_SANITIZED_DESC_CHARS = 1000     # Maximum characters preserved per description
MAX_TOTAL_PAYLOAD_CHARS = 15000     # Maximum combined text length sent to LLM
MAX_ALLOWED_SKILLS = 100
MAX_ALLOWED_PROJECTS = 20
MAX_ALLOWED_EXPERIENCES = 20


class PrivacyViolationError(ValueError):
    """Raised when forbidden sensitive PII attributes are detected in LLM payload."""
    pass


class OversizedInputError(ValueError):
    """Raised when payload or individual fields exceed safe operational size limits."""
    pass


def sanitize_text(text: Optional[str], candidate_name: Optional[str] = None) -> Optional[str]:
    """
    Sanitize a freeform text string by stripping PII (emails, phones, URLs, tokens,
    and occurrences of the candidate's name), then bounding the string length.
    """
    if text is None:
        return None

    if not isinstance(text, str):
        raise TypeError(f"Expected string for text sanitization, got {type(text).__name__}")

    # Reject grossly oversized single strings
    if len(text) > MAX_SINGLE_FIELD_CHARS:
        raise OversizedInputError(
            f"Input text length ({len(text)}) exceeds maximum single-field limit of {MAX_SINGLE_FIELD_CHARS} characters."
        )

    sanitized = text

    # 1. Redact Email Addresses first (before name scrubbing touches user handles)
    sanitized = EMAIL_PATTERN.sub("[EMAIL REDACTED]", sanitized)

    # 2. Redact Phone Numbers
    sanitized = PHONE_PATTERN.sub("[PHONE REDACTED]", sanitized)

    # 3. Redact Web & Profile URLs
    sanitized = URL_PATTERN.sub("[LINK REDACTED]", sanitized)

    # 4. Redact Cryptographic Tokens & Hashes
    sanitized = TOKEN_PATTERN.sub("[TOKEN REDACTED]", sanitized)

    # 5. Redact Candidate Name if supplied
    if candidate_name and isinstance(candidate_name, str):
        full_name = candidate_name.strip()
        if len(full_name) >= 3:
            sanitized = re.sub(
                r"\b" + re.escape(full_name) + r"\b",
                "[CANDIDATE]",
                sanitized,
                flags=re.IGNORECASE,
            )
            # Redact individual name components (e.g. first/last name >= 3 chars)
            for part in full_name.split():
                if len(part) >= 3 and part.lower() not in {"and", "the", "for", "with"}:
                    sanitized = re.sub(
                        r"\b" + re.escape(part) + r"\b",
                        "[CANDIDATE]",
                        sanitized,
                        flags=re.IGNORECASE,
                    )

    # Normalize excessive internal whitespace
    sanitized = re.sub(r"[ \t]+", " ", sanitized).strip()

    # Bounded truncation for description fields
    if len(sanitized) > MAX_SANITIZED_DESC_CHARS:
        sanitized = sanitized[:MAX_SANITIZED_DESC_CHARS].rstrip() + "..."

    return sanitized


def sanitize_dict_for_llm(data: Dict[str, Any]) -> SanitizedResumePayload:
    """
    Safely validate and sanitize an unvetted dictionary payload.
    Rejects directly passed sensitive attributes with PrivacyViolationError.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict payload, got {type(data).__name__}")

    # Defense-in-depth: Reject any forbidden key explicitly passed in payload
    found_forbidden = FORBIDDEN_PII_KEYS.intersection(data.keys())
    if found_forbidden:
        raise PrivacyViolationError(
            f"Direct submission of sensitive attribute(s) {sorted(list(found_forbidden))} "
            "to Gemini sanitizer is strictly forbidden."
        )

    return build_sanitized_payload(
        skills=data.get("skills", []),
        projects=data.get("projects", []),
        experience=data.get("experience", []),
        target_role_title=data.get("target_role_title"),
        missing_skills=data.get("missing_skills", []),
    )


def build_sanitized_payload(
    skills: Sequence[Any],
    projects: Optional[Sequence[Any]] = None,
    experience: Optional[Sequence[Any]] = None,
    target_role_title: Optional[str] = None,
    missing_skills: Optional[Sequence[Any]] = None,
    candidate_name: Optional[str] = None,
) -> SanitizedResumePayload:
    """
    Build a strictly typed, privacy-sanitized SanitizedResumePayload from
    raw extracted entities or models.
    """
    projects = projects or []
    experience = experience or []
    missing_skills = missing_skills or []

    # 1. Enforce item count boundaries
    if len(skills) > MAX_ALLOWED_SKILLS:
        raise OversizedInputError(
            f"Skills count ({len(skills)}) exceeds maximum allowed ({MAX_ALLOWED_SKILLS})."
        )
    if len(projects) > MAX_ALLOWED_PROJECTS:
        raise OversizedInputError(
            f"Projects count ({len(projects)}) exceeds maximum allowed ({MAX_ALLOWED_PROJECTS})."
        )
    if len(experience) > MAX_ALLOWED_EXPERIENCES:
        raise OversizedInputError(
            f"Experience count ({len(experience)}) exceeds maximum allowed ({MAX_ALLOWED_EXPERIENCES})."
        )

    # 2. Extract and sanitize skills
    sanitized_skills: List[str] = []
    for item in skills:
        name = getattr(item, "skill_name", None) or getattr(item, "name", None)
        if name is None and isinstance(item, dict):
            name = item.get("skill_name") or item.get("name")
        elif name is None and isinstance(item, str):
            name = item

        if name and isinstance(name, str):
            clean_name = sanitize_text(name.strip(), candidate_name=candidate_name)
            if clean_name:
                sanitized_skills.append(clean_name[:100])

    # 3. Extract and sanitize missing skills
    sanitized_missing_skills: List[str] = []
    for item in missing_skills:
        name = getattr(item, "skill_name", None) or getattr(item, "name", None)
        if name is None and isinstance(item, dict):
            name = item.get("skill_name") or item.get("name")
        elif name is None and isinstance(item, str):
            name = item

        if name and isinstance(name, str):
            clean_name = sanitize_text(name.strip(), candidate_name=candidate_name)
            if clean_name:
                sanitized_missing_skills.append(clean_name[:100])

    # 4. Extract and sanitize projects
    sanitized_projects: List[SanitizedProjectItem] = []
    for item in projects:
        if isinstance(item, dict):
            title = item.get("title", "")
            tech = item.get("technologies_used") or item.get("technologies")
            desc = item.get("description")
        else:
            title = getattr(item, "title", "")
            tech = getattr(item, "technologies_used", None) or getattr(item, "technologies", None)
            desc = getattr(item, "description", None)

        clean_title = sanitize_text(str(title).strip() or "Project", candidate_name=candidate_name)
        clean_tech = sanitize_text(tech.strip(), candidate_name=candidate_name) if tech else None
        clean_desc = sanitize_text(desc.strip(), candidate_name=candidate_name) if desc else None

        sanitized_projects.append(
            SanitizedProjectItem(
                title=(clean_title or "Project")[:150],
                technologies=clean_tech[:250] if clean_tech else None,
                description=clean_desc,
            )
        )

    # 5. Extract and sanitize experiences
    sanitized_experience: List[SanitizedExperienceItem] = []
    for item in experience:
        if isinstance(item, dict):
            role = item.get("role_title") or item.get("role", "")
            duration = item.get("duration")
            desc = item.get("description")
        else:
            role = getattr(item, "role_title", "") or getattr(item, "role", "")
            duration = getattr(item, "duration", None)
            desc = getattr(item, "description", None)

        clean_role = sanitize_text(str(role).strip() or "Professional Experience", candidate_name=candidate_name)
        clean_duration = sanitize_text(duration.strip(), candidate_name=candidate_name) if duration else None
        clean_desc = sanitize_text(desc.strip(), candidate_name=candidate_name) if desc else None

        sanitized_experience.append(
            SanitizedExperienceItem(
                role_title=(clean_role or "Role")[:150],
                duration=clean_duration[:100] if clean_duration else None,
                description=clean_desc,
            )
        )

    # 6. Sanitize Target Role
    clean_role_title = (
        sanitize_text(target_role_title.strip(), candidate_name=candidate_name)
        if target_role_title
        else None
    )
    if clean_role_title:
        clean_role_title = clean_role_title[:150]

    # 7. Check Total Text Length Across Entire Payload
    total_chars = (
        len(clean_role_title or "")
        + sum(len(s) for s in sanitized_skills)
        + sum(len(s) for s in sanitized_missing_skills)
        + sum(len(p.title) + len(p.technologies or "") + len(p.description or "") for p in sanitized_projects)
        + sum(len(e.role_title) + len(e.duration or "") + len(e.description or "") for e in sanitized_experience)
    )

    if total_chars > MAX_TOTAL_PAYLOAD_CHARS:
        raise OversizedInputError(
            f"Sanitized payload total character length ({total_chars}) exceeds safe maximum limit "
            f"of {MAX_TOTAL_PAYLOAD_CHARS} characters."
        )

    return SanitizedResumePayload(
        target_role_title=clean_role_title,
        skills=sanitized_skills,
        projects=sanitized_projects,
        experience=sanitized_experience,
        missing_skills=sanitized_missing_skills,
    )
