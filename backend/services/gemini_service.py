"""
CareerSync Google Gemini Service.

Generates structured, actionable resume improvement suggestions using the official
google-genai SDK, strictly bounded by the privacy sanitizer.

Guarantees:
1. Client initialization is backend-only using GEMINI_API_KEY and GEMINI_MODEL.
2. All input is sanitized via privacy_sanitizer before prompt assembly.
3. Candidate PII (name, email, phone), raw file contents, access tokens, and raw_text are NEVER transmitted.
4. Structured JSON output is enforced via Gemini GenerateContentConfig.
5. All errors (missing key, quota exceeded, network timeout, invalid JSON) raise specific GeminiServiceError subclasses with zero fallback fabrication.
6. Does NOT alter, calculate, or touch matching scores.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import ValidationError

from backend.config import settings
from backend.schemas.analysis import (
    ImprovementCategory,
    ResumeImprovementItem,
    ResumeImprovementResponse,
    SanitizedResumePayload,
    SuggestionPriority,
)
from backend.services.privacy_sanitizer import (
    OversizedInputError,
    PrivacyViolationError,
    build_sanitized_payload,
)

logger = logging.getLogger("careersync.services.gemini_service")

# -----------------------------------------------------------------------------
# Service Exceptions
# -----------------------------------------------------------------------------

class GeminiServiceError(Exception):
    """Base exception for all Gemini service failures."""
    pass


class GeminiConfigurationError(GeminiServiceError):
    """Raised when GEMINI_API_KEY is missing or improperly configured."""
    pass


class GeminiQuotaExceededError(GeminiServiceError):
    """Raised when the Gemini API quota or rate limit is exhausted (HTTP 429)."""
    pass


class GeminiNetworkError(GeminiServiceError):
    """Raised on connection failures, timeouts, or network drops."""
    pass


class GeminiResponseParsingError(GeminiServiceError):
    """Raised when Gemini output is not valid JSON or fails Pydantic schema validation."""
    pass


# -----------------------------------------------------------------------------
# Client Lifecycle & Initialization
# -----------------------------------------------------------------------------

def get_gemini_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Initialize and return a secure backend Gemini Client.
    Validates presence of API key without exposing it.
    """
    key = api_key or settings.GEMINI_API_KEY
    if not key or not key.strip():
        logger.error("Attempted to initialize Gemini client without GEMINI_API_KEY.")
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured on the backend. "
            "Please provide a valid Google AI Studio API key in the environment."
        )
    return genai.Client(api_key=key.strip())


# -----------------------------------------------------------------------------
# Prompt Assembly (Strictly Anonymized & Grounded)
# -----------------------------------------------------------------------------

SYSTEM_INSTRUCTION = (
    "You are an expert technical resume coach and career advisor for software engineering roles. "
    "Your objective is to review candidate qualifications and provide between 5 and 10 specific, actionable, "
    "and constructive resume improvement suggestions.\n\n"
    "STRICT RULES:\n"
    "1. Never invent credentials, degrees, employers, projects, or metrics that the candidate does not have.\n"
    "2. Ground every suggestion strictly in the supplied skills, projects, and experiences.\n"
    "3. Focus on phrasing impact, structural hierarchy, standardizing section formatting, and highlighting technical keywords.\n"
    "4. For any missing role requirements, advise how to showcase relevant transferable foundations or study pathways without claiming false proficiency.\n"
    "5. Every suggestion must provide a valid category ('STRUCTURE', 'PROJECTS', 'EXPERIENCE', 'SKILLS_FORMATTING', 'KEYWORDS') "
    "and priority ('HIGH', 'MEDIUM', 'LOW').\n"
    "6. Respond strictly with structured JSON matching the requested schema."
)


def build_improvement_prompt(payload: SanitizedResumePayload) -> str:
    """
    Construct a structured, privacy-sanitized prompt using ONLY approved fields.
    Zero candidate PII, raw text, or file bytes are permitted.
    """
    prompt_lines: List[str] = [
        "Please review the following candidate qualification profile and generate 5 to 10 actionable resume improvement suggestions:\n",
        f"Target Job Role: {payload.target_role_title or 'Software Engineering Professional'}\n",
    ]

    # Verified Skills
    if payload.skills:
        prompt_lines.append(f"Verified Technical Skills: {', '.join(payload.skills)}")
    else:
        prompt_lines.append("Verified Technical Skills: None extracted from resume")

    # Missing Role Skills / Gaps
    if payload.missing_skills:
        prompt_lines.append(f"Missing Target Role Skills: {', '.join(payload.missing_skills)}")

    # Sanitized Projects
    prompt_lines.append("\nHighlighted Projects:")
    if payload.projects:
        for idx, proj in enumerate(payload.projects, 1):
            tech_str = f" [Technologies: {proj.technologies}]" if proj.technologies else ""
            desc_str = f" - {proj.description}" if proj.description else ""
            prompt_lines.append(f"  {idx}. {proj.title}{tech_str}{desc_str}")
    else:
        prompt_lines.append("  (No specific project entries identified)")

    # Sanitized Experience
    prompt_lines.append("\nProfessional Experience:")
    if payload.experience:
        for idx, exp in enumerate(payload.experience, 1):
            dur_str = f" ({exp.duration})" if exp.duration else ""
            desc_str = f" - {exp.description}" if exp.description else ""
            prompt_lines.append(f"  {idx}. {exp.role_title}{dur_str}{desc_str}")
    else:
        prompt_lines.append("  (No specific professional experience entries identified)")

    prompt_lines.append(
        "\nTask: Generate between 5 and 10 prioritized resume improvement recommendations. "
        "Keep recommendations actionable, realistic, and strictly relevant to software engineering standards."
    )

    return "\n".join(prompt_lines)


# -----------------------------------------------------------------------------
# Structured Schema Sanitization & Compatibility
# -----------------------------------------------------------------------------

def strip_unsupported_schema_attributes(schema: Any) -> Any:
    """
    Recursively remove schema attributes unsupported by the Gemini Developer API
    (such as additional_properties / additionalProperties).
    """
    if isinstance(schema, genai_types.Schema):
        schema.additional_properties = None
        if schema.items:
            strip_unsupported_schema_attributes(schema.items)
        if schema.properties:
            for prop in schema.properties.values():
                strip_unsupported_schema_attributes(prop)
        if schema.any_of:
            for item in schema.any_of:
                strip_unsupported_schema_attributes(item)
    return schema


def build_gemini_response_schema(schema_type: Any = list[ResumeImprovementItem]) -> genai_types.Schema:
    """
    Build an API-compatible google.genai.types.Schema for structured output,
    guaranteeing that unsupported fields like additional_properties are stripped.
    """
    from google.genai import _transformers
    schema = _transformers.t_schema(None, schema_type)
    return strip_unsupported_schema_attributes(schema)


# -----------------------------------------------------------------------------
# Core Suggestion Generation Engine
# -----------------------------------------------------------------------------

def generate_resume_improvements_from_payload(
    resume_id: int,
    payload: SanitizedResumePayload,
    session_id: Optional[int] = None,
    target_role_id: Optional[int] = None,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
) -> ResumeImprovementResponse:
    """
    Execute Gemini API call using a pre-sanitized SanitizedResumePayload.
    Enforces structured JSON output and handles service exceptions safely.
    """
    if not isinstance(payload, SanitizedResumePayload):
        raise TypeError(f"Expected SanitizedResumePayload, got {type(payload).__name__}")

    target_model = model or settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
    gemini_client = client or get_gemini_client()

    prompt = build_improvement_prompt(payload)
    logger.info(
        "Invoking Gemini model '%s' for resume_id=%d (target_role='%s')",
        target_model,
        resume_id,
        payload.target_role_title,
    )

    # Configure structured JSON output schema matching list[ResumeImprovementItem]
    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=build_gemini_response_schema(list[ResumeImprovementItem]),
        temperature=0.2,
    )

    try:
        response = gemini_client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config,
        )
    except genai_errors.APIError as api_err:
        status_code = getattr(api_err, "code", None)
        message = str(api_err)
        logger.error("Gemini API error (code=%s): %s", status_code, message)
        if status_code == 429 or "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise GeminiQuotaExceededError(
                "Gemini API rate limit or quota exceeded. Please try again later."
            ) from api_err
        raise GeminiServiceError(f"Gemini API returned error: {message}") from api_err
    except (ConnectionError, TimeoutError, OSError) as net_err:
        logger.error("Network failure contacting Gemini: %s", net_err)
        raise GeminiNetworkError(
            f"Network error communicating with Gemini API: {net_err}"
        ) from net_err
    except Exception as exc:
        # Check if exception represents quota exhaustion or connection error
        exc_str = str(exc).lower()
        if "429" in exc_str or "quota" in exc_str or "resource_exhausted" in exc_str:
            raise GeminiQuotaExceededError(
                "Gemini API rate limit or quota exceeded. Please try again later."
            ) from exc
        if "timeout" in exc_str or "connection" in exc_str or "network" in exc_str:
            raise GeminiNetworkError(
                f"Network failure connecting to Gemini: {exc}"
            ) from exc
        logger.error("Unexpected error invoking Gemini: %s", exc)
        raise GeminiServiceError(f"Unexpected error in Gemini service: {exc}") from exc

    # Parse and validate returned JSON text
    raw_text = getattr(response, "text", None)
    if not raw_text or not raw_text.strip():
        logger.error("Gemini returned empty text response.")
        raise GeminiResponseParsingError("Gemini returned an empty response body.")

    try:
        parsed_data = json.loads(raw_text)
    except json.JSONDecodeError as json_err:
        logger.error("Failed to decode JSON from Gemini output: %s", json_err)
        raise GeminiResponseParsingError(
            f"Invalid JSON returned by Gemini: {json_err}"
        ) from json_err

    # Handle both top-level list or dictionary wrapper {"suggestions": [...]}
    if isinstance(parsed_data, dict):
        raw_items = parsed_data.get("suggestions", [])
    elif isinstance(parsed_data, list):
        raw_items = parsed_data
    else:
        raise GeminiResponseParsingError(
            f"Expected JSON list or object with 'suggestions' key, got {type(parsed_data).__name__}"
        )

    validated_suggestions: List[ResumeImprovementItem] = []
    for idx, item_data in enumerate(raw_items):
        try:
            item = ResumeImprovementItem.model_validate(item_data)
            validated_suggestions.append(item)
        except ValidationError as val_err:
            logger.warning("Suggestion item at index %d failed validation: %s", idx, val_err)
            raise GeminiResponseParsingError(
                f"Item at index {idx} failed schema validation: {val_err}"
            ) from val_err

    if not validated_suggestions:
        raise GeminiResponseParsingError("Gemini produced 0 valid suggestions.")

    # Bound output to at most 10 items
    final_suggestions = validated_suggestions[:10]

    return ResumeImprovementResponse(
        resume_id=resume_id,
        session_id=session_id,
        target_role_id=target_role_id,
        target_role_title=payload.target_role_title,
        total_suggestions=len(final_suggestions),
        suggestions=final_suggestions,
        message="Resume improvement suggestions generated successfully.",
        generated_at=datetime.now(timezone.utc),
    )


def generate_resume_improvement_suggestions(
    resume_id: int,
    skills: Sequence[Any],
    projects: Optional[Sequence[Any]] = None,
    experience: Optional[Sequence[Any]] = None,
    target_role_title: Optional[str] = None,
    target_role_id: Optional[int] = None,
    missing_skills: Optional[Sequence[Any]] = None,
    session_id: Optional[int] = None,
    candidate_name: Optional[str] = None,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
) -> ResumeImprovementResponse:
    """
    Main entry point for generating resume improvements.
    Sanitizes raw entities to eliminate all PII before invoking Gemini.
    """
    # 1. Sanitize input through privacy sanitizer
    sanitized_payload = build_sanitized_payload(
        skills=skills,
        projects=projects,
        experience=experience,
        target_role_title=target_role_title,
        missing_skills=missing_skills,
        candidate_name=candidate_name,
    )

    # 2. Invoke Gemini service with sanitized payload
    return generate_resume_improvements_from_payload(
        resume_id=resume_id,
        payload=sanitized_payload,
        session_id=session_id,
        target_role_id=target_role_id,
        client=client,
        model=model,
    )
