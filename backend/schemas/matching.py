from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class MatchedSkillDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    skill_name: str
    category: str
    importance: str
    weight: float
    extraction_source: Optional[str] = None


class MissingSkillDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    skill_name: str
    category: str
    importance: str
    weight: float


class JobRoleMatchScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_role_id: int
    job_role_title: str
    domain: str
    experience_level: str
    match_score: float
    matched_skills_count: int
    total_role_skills_count: int
    required_skills_match_percentage: float
    matched_skills: List[MatchedSkillDetail]
    missing_required_skills: List[MissingSkillDetail]
    missing_preferred_skills: List[MissingSkillDetail]
    score_breakdown: Dict[str, Any]
    explanation: str


class ResumeJobMatchingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate_name: Optional[str] = None
    total_candidate_skills: int
    matched_roles_count: int
    matches: List[JobRoleMatchScore]
    evaluated_at: datetime
