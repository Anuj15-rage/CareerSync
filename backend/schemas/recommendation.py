from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


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
