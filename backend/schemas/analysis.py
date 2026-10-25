from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ExtractedSkillItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    skill_name: str
    category: str
    extraction_source: str


class ExtractedEducationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    grade_or_cgpa: Optional[str] = None


class ExtractedProjectItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    technologies_used: Optional[str] = None


class ExtractedExperienceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    organization: Optional[str] = None
    role_title: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None


class CandidateInfo(BaseModel):
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    candidate_phone: Optional[str] = None


class ResumeAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    candidate: CandidateInfo
    skills: List[ExtractedSkillItem]
    education: List[ExtractedEducationItem]
    projects: List[ExtractedProjectItem]
    experience: List[ExtractedExperienceItem]
    unmatched_skills: List[str] = []
    message: str
    analyzed_at: datetime
