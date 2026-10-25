from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SkillGapItem(BaseModel):
    """Details of a single missing skill gap."""
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    skill_name: str
    category: str
    importance: str              # "REQUIRED" or "PREFERRED"
    weight: float                # e.g. 1.00 or 0.75
    gap_priority: str            # "CRITICAL_MISSING" or "SECONDARY_MISSING"
    reason: str                  # Transparent, dynamically generated reason


class PossessedSkillItem(BaseModel):
    """Details of a role skill already verified on the candidate's resume."""
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    skill_name: str
    category: str
    importance: str              # "REQUIRED" or "PREFERRED"
    weight: float
    extraction_source: Optional[str] = "SKILLS_SECTION"


class RoleSkillGapDetail(BaseModel):
    """Detailed skill gap analysis breakdown for a single job role."""
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    job_role_id: int
    job_role_title: str
    domain: str
    experience_level: str
    compatibility_score: float       # Overall weighted score (0.00 - 100.00)
    technical_skill_score: float     # Required skills match % (0.00 - 100.00)
    total_role_skills_count: int
    possessed_skills_count: int
    missing_skills_count: int
    critical_missing_count: int
    secondary_missing_count: int
    possessed_skills: List[PossessedSkillItem]
    critical_missing_skills: List[SkillGapItem]
    secondary_missing_skills: List[SkillGapItem]
    explanation: str
    created_at: datetime


class ResumeSkillGapsResponse(BaseModel):
    """Top-level response for candidate resume skill gap analysis."""
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate_name: Optional[str] = None
    total_candidate_skills: int
    roles_evaluated_count: int
    role_gaps: List[RoleSkillGapDetail]
    analyzed_at: datetime
