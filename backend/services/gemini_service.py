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
from backend.schemas.recommendation import (
    EnrichedLearningRoadmapResponse,
    EnrichedRoadmapItem,
    EnrichedRoadmapPhase,
    GeminiRoadmapItem,
    GeminiRoadmapOutput,
    GeminiRoadmapPhase,
    LearningRoadmapResponse,
    PersonalizedRoadmapResponse,
    RoadmapItem,
    RoadmapItemType,
    RoadmapPhase,
)
from backend.services.privacy_sanitizer import (
    OversizedInputError,
    PrivacyViolationError,
    build_sanitized_payload,
    sanitize_text,
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


# -----------------------------------------------------------------------------
# Learning Roadmap Generation Engine (Grounded & Privacy-Sanitized)
# -----------------------------------------------------------------------------

ROADMAP_SYSTEM_INSTRUCTION = (
    "You are an expert technical career mentor and curriculum advisor. "
    "Your objective is to design a personalized, sequenced learning roadmap that helps a candidate bridge specific skill gaps for their target role.\n\n"
    "STRICT RULES:\n"
    "1. You must ONLY reference the learning resources and certifications provided in the prompt using their exact database IDs (resource_id or certification_id).\n"
    "2. NEVER invent, fabricate, or hallucinate new courses, certifications, providers, or URLs.\n"
    "3. Every learning item in your roadmap must select from the approved resources and certifications listed in the prompt.\n"
    "4. Organize the roadmap into logical, sequential phases (e.g., Phase 1: Core Foundations, Phase 2: Advanced Implementations, Phase 3: Industry Certification).\n"
    "5. For every item, provide a clear, personalized explanation of why this specific resource helps the candidate bridge their identified skill gap.\n"
    "6. Respond strictly with JSON matching the requested schema."
)


def _normalize_resource_dict(item: Any) -> Dict[str, Any]:
    """Extract normalized resource dictionary from dict, Pydantic model, or DB instance."""
    if isinstance(item, dict):
        return {
            "resource_id": item.get("resource_id") or item.get("id"),
            "title": item.get("title") or "Learning Resource",
            "platform_name": item.get("platform_name") or item.get("platform") or "Platform",
            "targeted_skill_id": item.get("targeted_skill_id"),
            "targeted_skill_name": item.get("targeted_skill_name") or item.get("skill_name") or "Technical Skill",
            "difficulty_level": item.get("difficulty_level") or "BEGINNER",
            "is_free": item.get("is_free", True),
            "url": item.get("url"),
        }
    return {
        "resource_id": getattr(item, "resource_id", None) or getattr(item, "id", None),
        "title": getattr(item, "title", "Learning Resource"),
        "platform_name": getattr(item, "platform_name", None) or getattr(item, "platform", "Platform"),
        "targeted_skill_id": getattr(item, "targeted_skill_id", None),
        "targeted_skill_name": getattr(item, "targeted_skill_name", None) or getattr(item, "skill_name", "Technical Skill"),
        "difficulty_level": getattr(item, "difficulty_level", "BEGINNER"),
        "is_free": getattr(item, "is_free", True),
        "url": getattr(item, "url", None),
    }


def _normalize_certification_dict(item: Any) -> Dict[str, Any]:
    """Extract normalized certification dictionary from dict, Pydantic model, or DB instance."""
    if isinstance(item, dict):
        return {
            "certification_id": item.get("certification_id") or item.get("id"),
            "name": item.get("name") or item.get("title") or "Certification",
            "code": item.get("code"),
            "provider_name": item.get("provider_name") or item.get("provider") or "Accredited Body",
            "level": item.get("level") or "ENTRY",
            "targeted_skill_id": item.get("targeted_skill_id"),
            "targeted_skill_name": item.get("targeted_skill_name") or item.get("skill_name") or "Technical Skill",
            "official_url": item.get("official_url") or item.get("url"),
        }
    return {
        "certification_id": getattr(item, "certification_id", None) or getattr(item, "id", None),
        "name": getattr(item, "name", None) or getattr(item, "title", "Certification"),
        "code": getattr(item, "code", None),
        "provider_name": getattr(item, "provider_name", None) or getattr(item, "provider", "Accredited Body"),
        "level": getattr(item, "level", "ENTRY"),
        "targeted_skill_id": getattr(item, "targeted_skill_id", None),
        "targeted_skill_name": getattr(item, "targeted_skill_name", None) or getattr(item, "skill_name", "Technical Skill"),
        "official_url": getattr(item, "official_url", None) or getattr(item, "url", None),
    }


def build_roadmap_prompt(
    target_role_title: str,
    verified_skills: Sequence[str],
    missing_skills: Sequence[str],
    resources: Sequence[Dict[str, Any]],
    certifications: Sequence[Dict[str, Any]],
) -> str:
    """
    Construct a grounded, privacy-preserving prompt for learning roadmap generation.
    Supplies the exact catalog of database resources and certifications Gemini may reference.
    """
    prompt_lines: List[str] = [
        f"Target Career Role: {target_role_title}\n",
        f"Candidate's Verified Skills: {', '.join(verified_skills) if verified_skills else 'None verified'}",
        f"Identified Missing Skill Gaps: {', '.join(missing_skills) if missing_skills else 'None identified'}\n",
        "--- APPROVED DATABASE LEARNING RESOURCES ---",
    ]

    if resources:
        for r in resources:
            res_id = r["resource_id"]
            title = r.get("title", "Resource")
            platform = r.get("platform_name", "Platform")
            skill = r.get("targeted_skill_name", "General")
            cost = "Free" if r.get("is_free") else "Paid"
            diff = r.get("difficulty_level", "All Levels")
            prompt_lines.append(
                f"  • resource_id: {res_id} | Title: \"{title}\" | Platform: {platform} | Skill: {skill} | Cost: {cost} | Level: {diff}"
            )
    else:
        prompt_lines.append("  (No learning resources available)")

    prompt_lines.append("\n--- APPROVED DATABASE CERTIFICATIONS ---")
    if certifications:
        for c in certifications:
            cert_id = c["certification_id"]
            name = c.get("name", "Certification")
            provider = c.get("provider_name", "Provider")
            skill = c.get("targeted_skill_name", "General")
            level = c.get("level", "Standard")
            code_str = f" [{c.get('code')}]" if c.get("code") else ""
            prompt_lines.append(
                f"  • certification_id: {cert_id} | Name: \"{name}\"{code_str} | Provider: {provider} | Skill: {skill} | Level: {level}"
            )
    else:
        prompt_lines.append("  (No certifications available)")

    prompt_lines.append(
        "\nTask: Create a cohesive, phased learning roadmap selecting from the approved resources and certifications above. "
        "Sequence them logically so foundational topics precede advanced topics. "
        "For each item, specify item_type ('LEARNING_RESOURCE' or 'CERTIFICATION'), reference its exact database ID, "
        "and provide a personalized explanation of why this resource is valuable given the candidate's background and skill gaps. "
        "Do NOT invent, fabricate, or mention any resources outside of this approved list."
    )

    return "\n".join(prompt_lines)


def generate_learning_roadmap(
    resume_id: int,
    target_role_title: str,
    target_role_id: Optional[int] = None,
    verified_skills: Optional[Sequence[Any]] = None,
    missing_skills: Optional[Sequence[Any]] = None,
    learning_resources: Optional[Sequence[Any]] = None,
    certifications: Optional[Sequence[Any]] = None,
    candidate_name: Optional[str] = None,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
) -> EnrichedLearningRoadmapResponse:
    """
    Generate a personalized, phased learning roadmap using Google Gemini.

    Guarantees:
    1. Zero PII transmission: candidate name, email, phone, raw resume text, and tokens are scrubbed.
    2. Strict database grounding: Gemini is restricted to referencing supplied resource and certification IDs.
    3. Rejects any output referencing unsupplied, non-existent, or hallucinated IDs.
    4. Validates structured JSON matching PersonalizedRoadmapResponse schema.
    5. Returns EnrichedLearningRoadmapResponse populated with verified database titles, URLs, and platforms.
    6. Robust error handling without fake or rule-based fallback fabrication.
    """
    # 1. Sanitize text and skill strings
    clean_role_title = (
        sanitize_text(str(target_role_title).strip(), candidate_name=candidate_name)
        if target_role_title
        else "Software Engineering Professional"
    ) or "Software Engineering Professional"

    clean_verified_skills: List[str] = []
    for s in (verified_skills or []):
        s_name = getattr(s, "name", None) or getattr(s, "skill_name", None) or (s if isinstance(s, str) else None)
        if s_name:
            clean_s = sanitize_text(str(s_name).strip(), candidate_name=candidate_name)
            if clean_s:
                clean_verified_skills.append(clean_s[:100])

    clean_missing_skills: List[str] = []
    for s in (missing_skills or []):
        s_name = getattr(s, "name", None) or getattr(s, "skill_name", None) or (s if isinstance(s, str) else None)
        if s_name:
            clean_s = sanitize_text(str(s_name).strip(), candidate_name=candidate_name)
            if clean_s:
                clean_missing_skills.append(clean_s[:100])

    # 2. Normalize and index database resources and certifications
    normalized_resources: List[Dict[str, Any]] = [
        _normalize_resource_dict(r) for r in (learning_resources or [])
    ]
    normalized_certifications: List[Dict[str, Any]] = [
        _normalize_certification_dict(c) for c in (certifications or [])
    ]

    resource_map: Dict[int, Dict[str, Any]] = {
        r["resource_id"]: r for r in normalized_resources if r.get("resource_id") is not None
    }
    certification_map: Dict[int, Dict[str, Any]] = {
        c["certification_id"]: c for c in normalized_certifications if c.get("certification_id") is not None
    }

    allowed_resource_ids = set(resource_map.keys())
    allowed_certification_ids = set(certification_map.keys())

    # Fast return if no resources or certifications exist
    if not allowed_resource_ids and not allowed_certification_ids:
        logger.info(
            "No learning resources or certifications supplied for resume %s; returning empty roadmap.",
            resume_id,
        )
        return EnrichedLearningRoadmapResponse(
            resume_id=resume_id,
            target_role_id=target_role_id,
            target_role_title=clean_role_title,
            total_phases=0,
            total_items=0,
            phases=[],
            summary=f"No skill gaps or learning resources required for {clean_role_title}.",
            generated_at=datetime.now(timezone.utc),
        )

    # 3. Assemble prompt and configuration
    prompt = build_roadmap_prompt(
        target_role_title=clean_role_title,
        verified_skills=clean_verified_skills,
        missing_skills=clean_missing_skills,
        resources=list(resource_map.values()),
        certifications=list(certification_map.values()),
    )

    target_model = model or settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
    gemini_client = client or get_gemini_client()

    logger.info(
        "Invoking Gemini model '%s' for learning roadmap (resume_id=%d, role='%s', resources=%d, certs=%d)",
        target_model,
        resume_id,
        clean_role_title,
        len(allowed_resource_ids),
        len(allowed_certification_ids),
    )

    config = genai_types.GenerateContentConfig(
        system_instruction=ROADMAP_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=build_gemini_response_schema(GeminiRoadmapOutput),
        temperature=0.2,
    )

    # 4. Invoke Gemini with standardized error handling
    try:
        response = gemini_client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config,
        )
    except genai_errors.APIError as api_err:
        status_code = getattr(api_err, "code", None)
        message = str(api_err)
        logger.error("Gemini API error generating roadmap (code=%s): %s", status_code, message)
        if status_code == 429 or "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise GeminiQuotaExceededError(
                "Gemini API rate limit or quota exceeded. Please try again later."
            ) from api_err
        raise GeminiServiceError(f"Gemini API returned error: {message}") from api_err
    except (ConnectionError, TimeoutError, OSError) as net_err:
        logger.error("Network failure contacting Gemini for roadmap: %s", net_err)
        raise GeminiNetworkError(
            f"Network error communicating with Gemini API: {net_err}"
        ) from net_err
    except Exception as exc:
        exc_str = str(exc).lower()
        if "429" in exc_str or "quota" in exc_str or "resource_exhausted" in exc_str:
            raise GeminiQuotaExceededError(
                "Gemini API rate limit or quota exceeded. Please try again later."
            ) from exc
        if "timeout" in exc_str or "connection" in exc_str or "network" in exc_str:
            raise GeminiNetworkError(
                f"Network failure connecting to Gemini: {exc}"
            ) from exc
        logger.error("Unexpected error invoking Gemini roadmap: %s", exc)
        raise GeminiServiceError(f"Unexpected error in Gemini service: {exc}") from exc

    # 5. Parse and validate JSON structure
    raw_text = getattr(response, "text", None)
    if not raw_text or not raw_text.strip():
        logger.error("Gemini returned empty text response for learning roadmap.")
        raise GeminiResponseParsingError("Gemini returned an empty response body.")

    try:
        parsed_data = json.loads(raw_text)
    except json.JSONDecodeError as json_err:
        logger.error("Failed to decode JSON from Gemini roadmap output: %s", json_err)
        raise GeminiResponseParsingError(
            f"Invalid JSON returned by Gemini: {json_err}"
        ) from json_err

    # Normalize structure to dict with 'phases'
    if isinstance(parsed_data, list):
        parsed_data = {"phases": parsed_data}
    elif not isinstance(parsed_data, dict):
        raise GeminiResponseParsingError(
            f"Expected JSON object or list for learning roadmap, got {type(parsed_data).__name__}"
        )

    # First validate with simplified GeminiRoadmapOutput schema
    try:
        gemini_output = GeminiRoadmapOutput.model_validate(parsed_data)
    except ValidationError as val_err:
        logger.warning("Gemini roadmap output failed schema validation: %s", val_err)
        raise GeminiResponseParsingError(
            f"Roadmap failed schema validation: {val_err}"
        ) from val_err

    # Construct and strictly validate backend models (RoadmapItem, RoadmapPhase, PersonalizedRoadmapResponse)
    validated_phases: List[RoadmapPhase] = []
    for phase_idx, phase in enumerate(gemini_output.phases, 1):
        validated_items: List[RoadmapItem] = []
        for item_idx, item in enumerate(phase.items, 1):
            raw_type = (item.item_type or "").strip().upper()
            if raw_type == "LEARNING_RESOURCE":
                item_type = RoadmapItemType.LEARNING_RESOURCE
            elif raw_type == "CERTIFICATION":
                item_type = RoadmapItemType.CERTIFICATION
            else:
                raise GeminiResponseParsingError(
                    f"Invalid item_type '{item.item_type}'. Must be LEARNING_RESOURCE or CERTIFICATION."
                )

            try:
                val_item = RoadmapItem(
                    item_type=item_type,
                    resource_id=item.resource_id,
                    certification_id=item.certification_id,
                    targeted_skill_name=item.targeted_skill_name or "Technical Skill",
                    personalized_explanation=item.personalized_explanation,
                    sequence_order=item_idx,
                )
                validated_items.append(val_item)
            except ValidationError as item_err:
                logger.warning("Roadmap item failed validation: %s", item_err)
                raise GeminiResponseParsingError(
                    f"Roadmap item failed validation: {item_err}"
                ) from item_err

        try:
            val_phase = RoadmapPhase(
                phase_number=phase.phase_number if (phase.phase_number and phase.phase_number > 0) else phase_idx,
                title=phase.title,
                description=phase.description,
                items=validated_items,
            )
            validated_phases.append(val_phase)
        except ValidationError as phase_err:
            logger.warning("Roadmap phase failed validation: %s", phase_err)
            raise GeminiResponseParsingError(
                f"Roadmap phase failed validation: {phase_err}"
            ) from phase_err

    try:
        roadmap_obj = PersonalizedRoadmapResponse(
            resume_id=resume_id,
            target_role_id=target_role_id,
            target_role_title=clean_role_title,
            total_phases=len(validated_phases),
            total_items=sum(len(p.items) for p in validated_phases),
            phases=validated_phases,
            summary=gemini_output.summary or f"Personalized learning roadmap tailored for {clean_role_title}.",
            generated_at=datetime.now(timezone.utc),
        )
    except ValidationError as resp_err:
        logger.warning("PersonalizedRoadmapResponse validation failed: %s", resp_err)
        raise GeminiResponseParsingError(
            f"Roadmap validation failed: {resp_err}"
        ) from resp_err

    # 6. Strict ID grounding verification and database enrichment
    enriched_phases: List[EnrichedRoadmapPhase] = []
    total_items_count = 0

    for phase in roadmap_obj.phases:
        enriched_items: List[EnrichedRoadmapItem] = []
        for item in phase.items:
            if item.item_type == RoadmapItemType.LEARNING_RESOURCE:
                if item.resource_id not in allowed_resource_ids:
                    logger.error(
                        "Gemini referenced unapproved resource_id=%s (allowed: %s)",
                        item.resource_id,
                        allowed_resource_ids,
                    )
                    raise GeminiResponseParsingError(
                        f"Roadmap item referenced unapproved or non-existent resource_id: {item.resource_id}. "
                        "Only verified database resources may be used."
                    )
                db_res = resource_map[item.resource_id]
                enriched_items.append(
                    EnrichedRoadmapItem(
                        item_type=item.item_type,
                        resource_id=item.resource_id,
                        certification_id=None,
                        targeted_skill_id=item.targeted_skill_id or db_res.get("targeted_skill_id"),
                        targeted_skill_name=item.targeted_skill_name or db_res.get("targeted_skill_name", "Skill"),
                        personalized_explanation=item.personalized_explanation,
                        sequence_order=item.sequence_order,
                        title=db_res.get("title"),
                        platform_or_provider=db_res.get("platform_name"),
                        url=db_res.get("url"),
                        difficulty_or_level=db_res.get("difficulty_level"),
                        is_free=db_res.get("is_free"),
                    )
                )
            elif item.item_type == RoadmapItemType.CERTIFICATION:
                if item.certification_id not in allowed_certification_ids:
                    logger.error(
                        "Gemini referenced unapproved certification_id=%s (allowed: %s)",
                        item.certification_id,
                        allowed_certification_ids,
                    )
                    raise GeminiResponseParsingError(
                        f"Roadmap item referenced unapproved or non-existent certification_id: {item.certification_id}. "
                        "Only verified database certifications may be used."
                    )
                db_cert = certification_map[item.certification_id]
                enriched_items.append(
                    EnrichedRoadmapItem(
                        item_type=item.item_type,
                        resource_id=None,
                        certification_id=item.certification_id,
                        targeted_skill_id=item.targeted_skill_id or db_cert.get("targeted_skill_id"),
                        targeted_skill_name=item.targeted_skill_name or db_cert.get("targeted_skill_name", "Skill"),
                        personalized_explanation=item.personalized_explanation,
                        sequence_order=item.sequence_order,
                        title=db_cert.get("name"),
                        platform_or_provider=db_cert.get("provider_name"),
                        url=db_cert.get("official_url"),
                        difficulty_or_level=db_cert.get("level"),
                        is_free=False,
                    )
                )
            total_items_count += 1

        enriched_phases.append(
            EnrichedRoadmapPhase(
                phase_number=phase.phase_number,
                title=phase.title,
                description=phase.description,
                items=enriched_items,
            )
        )

    if total_items_count == 0 and (allowed_resource_ids or allowed_certification_ids):
        raise GeminiResponseParsingError("Gemini generated 0 roadmap items from the provided resources.")

    return EnrichedLearningRoadmapResponse(
        resume_id=resume_id,
        target_role_id=target_role_id,
        target_role_title=clean_role_title,
        total_phases=len(enriched_phases),
        total_items=total_items_count,
        phases=enriched_phases,
        summary=roadmap_obj.summary or f"Personalized learning roadmap tailored for {clean_role_title}.",
        generated_at=datetime.now(timezone.utc),
    )
