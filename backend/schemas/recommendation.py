from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CareerRecommendationItem(BaseModel):
    """Detailed recommendation record for a specific job role."""
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: int
    session_id: int
    job_role_id: int
    job_role_title: str
    domain: str
    experience_level: str
    match_percentage: float       # Compatibility score (0.00 - 100.00)
    technical_skill_score: float  # Required skills coverage % (0.00 - 100.00)
    rank: int                     # 1 = top recommendation
    fit_level: str                # STRONG_MATCH, MODERATE_MATCH, POTENTIAL_GROWTH, NO_MATCH
    rationale: str                # Explainable evidence text
    matched_skills_count: int
    missing_required_count: int
    missing_preferred_count: int
    matched_skills: List[str]
    missing_required_skills: List[str]
    missing_preferred_skills: List[str]
    created_at: datetime


class ResumeCareerRecommendationsResponse(BaseModel):
    """Top-level response for candidate career recommendations."""
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate_name: Optional[str] = None
    total_candidate_skills: int
    total_recommendations: int
    top_recommendation: Optional[str] = None
    recommendations: List[CareerRecommendationItem]
    generated_at: datetime


class ResourceRecommendationItem(BaseModel):
    """Learning resource recommendation targeting a specific missing skill gap."""
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: int
    session_id: int
    resource_id: int
    title: str
    platform_name: str
    url: str
    resource_type: str
    difficulty_level: str
    is_free: bool
    targeted_skill_id: int
    targeted_skill_name: str
    gap_priority: str            # CRITICAL_MISSING or SECONDARY_MISSING
    priority_order: int
    created_at: datetime


class CertificationRecommendationItem(BaseModel):
    """Certification recommendation targeting a specific missing skill gap."""
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: int
    session_id: int
    certification_id: int
    name: str
    code: Optional[str] = None
    provider_name: str
    level: str
    official_url: str
    targeted_skill_id: int
    targeted_skill_name: str
    gap_priority: str            # CRITICAL_MISSING or SECONDARY_MISSING
    rationale: str
    created_at: datetime


class RoleLearningResourcesResponse(BaseModel):
    """Learning resources recommended for a specific target job role."""
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    job_role_id: int
    job_role_title: str
    total_resources: int
    resources: List[ResourceRecommendationItem]


class ResumeLearningResourcesResponse(BaseModel):
    """Top-level response for candidate learning resource recommendations."""
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate_name: Optional[str] = None
    total_roles: int
    total_resources: int
    roles: List[RoleLearningResourcesResponse]
    retrieved_at: datetime


class RoleCertificationsResponse(BaseModel):
    """Certifications recommended for a specific target job role."""
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    job_role_id: int
    job_role_title: str
    total_certifications: int
    certifications: List[CertificationRecommendationItem]


class ResumeCertificationsResponse(BaseModel):
    """Top-level response for candidate certification recommendations."""
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate_name: Optional[str] = None
    total_roles: int
    total_certifications: int
    roles: List[RoleCertificationsResponse]
    retrieved_at: datetime


class RoleConsolidatedRecommendations(BaseModel):
    """Consolidated recommendations (resources + certs) for a job role."""
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    job_role_id: int
    job_role_title: str
    compatibility_score: float
    total_resources: int
    total_certifications: int
    learning_resources: List[ResourceRecommendationItem]
    certifications: List[CertificationRecommendationItem]


class ResumeConsolidatedRecommendationsResponse(BaseModel):
    """Consolidated response across all roles for a resume."""
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate_name: Optional[str] = None
    total_roles_evaluated: int
    total_resources: int
    total_certifications: int
    roles: List[RoleConsolidatedRecommendations]
    generated_at: datetime


# -----------------------------------------------------------------------------
# Gemini-Powered Personalized Learning Roadmap Schemas
# -----------------------------------------------------------------------------

def _strip_additional_properties_from_schema(schema: dict) -> None:
    """
    Recursively remove attributes unsupported by google.genai.types.Schema:
    - additionalProperties
    - exclusiveMinimum / exclusiveMaximum
    """
    schema.pop("additionalProperties", None)
    schema.pop("exclusiveMinimum", None)
    schema.pop("exclusiveMaximum", None)
    if "properties" in schema and isinstance(schema["properties"], dict):
        for prop in schema["properties"].values():
            if isinstance(prop, dict):
                _strip_additional_properties_from_schema(prop)
    if "items" in schema and isinstance(schema["items"], dict):
        _strip_additional_properties_from_schema(schema["items"])
    if "$defs" in schema and isinstance(schema["$defs"], dict):
        for d in schema["$defs"].values():
            if isinstance(d, dict):
                _strip_additional_properties_from_schema(d)


class RoadmapItemType(str, Enum):
    """Supported item types in the personalized learning roadmap."""
    LEARNING_RESOURCE = "LEARNING_RESOURCE"
    CERTIFICATION = "CERTIFICATION"


class RoadmapItem(BaseModel):
    """
    Individual learning roadmap item referencing an existing database resource or certification.

    Guarantees:
    - References existing database rows by resource_id or certification_id.
    - Strictly forbids generating arbitrary URLs, course titles, or new resources.
    - Validates that exactly one ID matching item_type is provided.
    - Bounded string lengths and no unexpected fields permitted.
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    item_type: RoadmapItemType = Field(
        ...,
        description="Type of learning item: LEARNING_RESOURCE or CERTIFICATION",
    )
    resource_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Existing database LearningResource ID (required if item_type is LEARNING_RESOURCE)",
    )
    certification_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Existing database Certification ID (required if item_type is CERTIFICATION)",
    )
    targeted_skill_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Database ID of the targeted missing skill gap, if mapped",
    )
    targeted_skill_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the missing skill gap addressed by this item",
    )
    personalized_explanation: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Personalized rationale explaining why this resource or certification is useful for the candidate",
    )
    sequence_order: int = Field(
        default=1,
        ge=1,
        description="1-based ordering sequence of this item within the phase",
    )

    @model_validator(mode="after")
    def validate_reference_id(self) -> "RoadmapItem":
        if self.item_type == RoadmapItemType.LEARNING_RESOURCE:
            if self.resource_id is None:
                raise ValueError("resource_id is required when item_type is LEARNING_RESOURCE")
            if self.certification_id is not None:
                raise ValueError("certification_id must not be provided when item_type is LEARNING_RESOURCE")
        elif self.item_type == RoadmapItemType.CERTIFICATION:
            if self.certification_id is None:
                raise ValueError("certification_id is required when item_type is CERTIFICATION")
            if self.resource_id is not None:
                raise ValueError("resource_id must not be provided when item_type is CERTIFICATION")
        return self


class RoadmapPhase(BaseModel):
    """
    Ordered phase within the personalized learning roadmap.
    Groups learning items logically by progression (e.g. foundational, core, specialization).
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    phase_number: int = Field(
        ...,
        ge=1,
        le=20,
        description="Sequential phase number (1, 2, 3...)",
    )
    title: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Title of the learning phase (e.g. 'Phase 1: Foundational Database Skills')",
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Short description of the phase objectives and scope",
    )
    items: List[RoadmapItem] = Field(
        default_factory=list,
        max_length=30,
        description="Ordered list of learning items belonging to this phase",
    )


class PersonalizedRoadmapResponse(BaseModel):
    """
    Top-level response envelope for a personalized learning roadmap.
    Contains target role information, total phase count, ordered phases, and generation timestamp.
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    resume_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Unique resume identifier",
    )
    target_role_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Target job role ID evaluated",
    )
    target_role_title: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Target job role title",
    )
    total_phases: int = Field(
        ...,
        ge=0,
        description="Total number of learning roadmap phases",
    )
    total_items: int = Field(
        default=0,
        ge=0,
        description="Total number of learning items across all phases",
    )
    phases: List[RoadmapPhase] = Field(
        default_factory=list,
        max_length=20,
        description="Ordered list of learning phases",
    )
    summary: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="High-level roadmap overview or strategic guidance",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the roadmap was generated",
    )





# Alias for backward and forward compatibility
LearningRoadmapResponse = PersonalizedRoadmapResponse


class EnrichedRoadmapItem(RoadmapItem):
    """
    Roadmap item enriched with verified metadata from the database.
    Populated by the backend service from existing database rows; never generated as arbitrary new resources.
    """
    title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Verified title from the database",
    )
    platform_or_provider: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Verified platform name or certification provider from the database",
    )
    url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Verified official URL from the database",
    )
    difficulty_or_level: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Verified difficulty level or certification level",
    )
    is_free: Optional[bool] = Field(
        default=None,
        description="Whether the resource is free to access",
    )


class EnrichedRoadmapPhase(BaseModel):
    """
    Phase containing roadmap items enriched with verified database metadata.
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    phase_number: int = Field(
        ...,
        ge=1,
        le=20,
        description="Sequential phase number",
    )
    title: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Phase title",
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Phase description",
    )
    items: List[EnrichedRoadmapItem] = Field(
        default_factory=list,
        max_length=30,
        description="Enriched learning items",
    )


class EnrichedLearningRoadmapResponse(BaseModel):
    """
    Full response containing verified database details for all roadmap items.
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    resume_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Unique resume identifier",
    )
    target_role_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Target job role ID evaluated",
    )
    target_role_title: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Target job role title",
    )
    total_phases: int = Field(
        ...,
        ge=0,
        description="Total number of learning roadmap phases",
    )
    total_items: int = Field(
        default=0,
        ge=0,
        description="Total number of learning items across all phases",
    )
    phases: List[EnrichedRoadmapPhase] = Field(
        default_factory=list,
        max_length=20,
        description="Ordered list of enriched learning phases",
    )
    summary: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="High-level roadmap overview or strategic guidance",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the roadmap was generated",
    )


# -----------------------------------------------------------------------------
# Simplified Schemas for Gemini Constrained Structured Output
# -----------------------------------------------------------------------------

class GeminiRoadmapItem(BaseModel):
    """
    Lightweight learning item schema specifically designed for Gemini structured output.
    Avoids nested counting constraints, string length bounds, and integer ranges
    to prevent FSM state explosion in Gemini's constrained decoding grammar.
    """
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    item_type: str = Field(
        ...,
        description="Type: 'LEARNING_RESOURCE' or 'CERTIFICATION'",
    )
    resource_id: Optional[int] = Field(
        default=None,
        description="Approved database resource_id if LEARNING_RESOURCE, else null",
    )
    certification_id: Optional[int] = Field(
        default=None,
        description="Approved database certification_id if CERTIFICATION, else null",
    )
    targeted_skill_name: Optional[str] = Field(
        default=None,
        description="Name of the targeted missing skill gap",
    )
    personalized_explanation: str = Field(
        ...,
        description="Personalized rationale explaining why this resource helps bridge the candidate's skill gap",
    )


class GeminiRoadmapPhase(BaseModel):
    """
    Lightweight phase schema specifically designed for Gemini structured output.
    """
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    phase_number: int = Field(
        ...,
        description="Sequential phase number (1, 2, 3...)",
    )
    title: str = Field(
        ...,
        description="Title of this learning phase",
    )
    description: str = Field(
        ...,
        description="Objectives and scope of this phase",
    )
    items: List[GeminiRoadmapItem] = Field(
        default_factory=list,
        description="Approved learning resources or certifications assigned to this phase",
    )


class GeminiRoadmapOutput(BaseModel):
    """
    Lightweight top-level roadmap container specifically for Gemini structured output.
    Eliminates redundant metadata fields known by the backend (resume_id, target_role_id,
    target_role_title, total_phases, total_items, generated_at) to minimize schema states.
    """
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra=_strip_additional_properties_from_schema,
    )

    summary: Optional[str] = Field(
        default=None,
        description="Strategic summary of the personalized roadmap",
    )
    phases: List[GeminiRoadmapPhase] = Field(
        default_factory=list,
        description="Ordered sequence of learning phases",
    )




