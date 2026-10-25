"""
CareerSync SQLAlchemy ORM Models
Corresponds 1:1 to the 19 normalized MySQL tables in careersync_db.
"""
from backend.database import Base
from backend.models.analysis import (
    AnalysisSession,
    CareerRecommendation,
    ResumeImprovementSuggestion,
    SessionCertificationRecommendation,
    SessionResourceRecommendation,
    SkillGap,
)
from backend.models.job_role import JobRole
from backend.models.resource import (
    Certification,
    CertificationProvider,
    LearningResource,
)
from backend.models.resume import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
)
from backend.models.skill import (
    CertificationSkill,
    JobRoleSkill,
    ResourceSkill,
    ResumeSkill,
    Skill,
)

__all__ = [
    "Base",
    # Skills
    "Skill",
    "ResumeSkill",
    "JobRoleSkill",
    "ResourceSkill",
    "CertificationSkill",
    # Resumes
    "Resume",
    "ResumeEducation",
    "ResumeProject",
    "ResumeExperience",
    # Job Roles
    "JobRole",
    # Resources & Certifications
    "CertificationProvider",
    "Certification",
    "LearningResource",
    # Analysis & Recommendations
    "AnalysisSession",
    "SkillGap",
    "CareerRecommendation",
    "SessionResourceRecommendation",
    "SessionCertificationRecommendation",
    "ResumeImprovementSuggestion",
]
