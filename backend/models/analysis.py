from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, SMALLINT
from sqlalchemy.orm import relationship

from backend.database import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resume_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("resumes.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    job_role_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("job_roles.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    target_role_title = Column(String(150), nullable=False)
    target_job_description = Column(Text, nullable=False)
    compatibility_score = Column(Numeric(5, 2), nullable=True)
    technical_skill_score = Column(Numeric(5, 2), nullable=True)
    education_score = Column(Numeric(5, 2), nullable=True)
    experience_score = Column(Numeric(5, 2), nullable=True)
    keyword_score = Column(Numeric(5, 2), nullable=True)
    methodology_notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        CheckConstraint(
            "compatibility_score IS NULL OR (compatibility_score >= 0.00 AND compatibility_score <= 100.00)",
            name="chk_compatibility_score",
        ),
        CheckConstraint(
            "technical_skill_score IS NULL OR (technical_skill_score >= 0.00 AND technical_skill_score <= 100.00)",
            name="chk_technical_score",
        ),
        CheckConstraint(
            "education_score IS NULL OR (education_score >= 0.00 AND education_score <= 100.00)",
            name="chk_education_score",
        ),
        CheckConstraint(
            "experience_score IS NULL OR (experience_score >= 0.00 AND experience_score <= 100.00)",
            name="chk_experience_score",
        ),
        CheckConstraint(
            "keyword_score IS NULL OR (keyword_score >= 0.00 AND keyword_score <= 100.00)",
            name="chk_keyword_score",
        ),
    )

    # Relationships
    resume = relationship("Resume", back_populates="analysis_sessions")
    job_role = relationship("JobRole")
    skill_gaps = relationship(
        "SkillGap", back_populates="session", cascade="all, delete-orphan"
    )
    career_recommendations = relationship(
        "CareerRecommendation", back_populates="session", cascade="all, delete-orphan"
    )
    resource_recommendations = relationship(
        "SessionResourceRecommendation",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    certification_recommendations = relationship(
        "SessionCertificationRecommendation",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    improvement_suggestions = relationship(
        "ResumeImprovementSuggestion",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AnalysisSession(id={self.id}, resume_id={self.resume_id}, role='{self.target_role_title}', score={self.compatibility_score})>"


class SkillGap(Base):
    __tablename__ = "skill_gaps"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    session_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("skills.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    gap_priority = Column(
        Enum(
            "CRITICAL_MISSING",
            "SECONDARY_MISSING",
            "UNVERIFIED_CONTEXT",
            name="gap_priority_enum",
        ),
        nullable=False,
        index=True,
    )
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "skill_id", name="uq_session_gap_skill"),
    )

    # Relationships
    session = relationship("AnalysisSession", back_populates="skill_gaps")
    skill = relationship("Skill")


class CareerRecommendation(Base):
    __tablename__ = "career_recommendations"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    session_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    job_role_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("job_roles.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    match_percentage = Column(Numeric(5, 2), nullable=False)
    rationale = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "job_role_id", name="uq_session_career_role"),
        CheckConstraint(
            "match_percentage >= 0.00 AND match_percentage <= 100.00",
            name="chk_career_match_percentage",
        ),
    )

    # Relationships
    session = relationship("AnalysisSession", back_populates="career_recommendations")
    job_role = relationship("JobRole")


class SessionResourceRecommendation(Base):
    __tablename__ = "session_resource_recommendations"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    session_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = Column(INTEGER(unsigned=True), nullable=False, index=True)
    skill_id = Column(INTEGER(unsigned=True), nullable=False, index=True)
    priority_order = Column(SMALLINT(unsigned=True), nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "session_id", "resource_id", "skill_id", name="uq_session_resource_skill"
        ),
        ForeignKeyConstraint(
            ["resource_id", "skill_id"],
            ["resource_skills.resource_id", "resource_skills.skill_id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="fk_resrec_resource_skill",
        ),
    )

    # Relationships
    session = relationship(
        "AnalysisSession", back_populates="resource_recommendations"
    )
    resource_skill = relationship(
        "ResourceSkill",
        primaryjoin="and_(SessionResourceRecommendation.resource_id == ResourceSkill.resource_id, SessionResourceRecommendation.skill_id == ResourceSkill.skill_id)",
        foreign_keys=[resource_id, skill_id],
    )


class SessionCertificationRecommendation(Base):
    __tablename__ = "session_certification_recommendations"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    session_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    certification_id = Column(INTEGER(unsigned=True), nullable=False, index=True)
    skill_id = Column(INTEGER(unsigned=True), nullable=False, index=True)
    rationale = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "session_id", "certification_id", "skill_id", name="uq_session_cert_skill"
        ),
        ForeignKeyConstraint(
            ["certification_id", "skill_id"],
            ["certification_skills.certification_id", "certification_skills.skill_id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="fk_certrec_cert_skill",
        ),
    )

    # Relationships
    session = relationship(
        "AnalysisSession", back_populates="certification_recommendations"
    )
    certification_skill = relationship(
        "CertificationSkill",
        primaryjoin="and_(SessionCertificationRecommendation.certification_id == CertificationSkill.certification_id, SessionCertificationRecommendation.skill_id == CertificationSkill.skill_id)",
        foreign_keys=[certification_id, skill_id],
    )


class ResumeImprovementSuggestion(Base):
    __tablename__ = "resume_improvement_suggestions"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    session_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(
        Enum(
            "STRUCTURE",
            "PROJECTS",
            "EXPERIENCE",
            "SKILLS_FORMATTING",
            "KEYWORDS",
            name="improvement_category_enum",
        ),
        nullable=False,
    )
    suggestion = Column(Text, nullable=False)
    priority = Column(
        Enum("HIGH", "MEDIUM", "LOW", name="suggestion_priority_enum"),
        nullable=False,
        default="MEDIUM",
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    session = relationship(
        "AnalysisSession", back_populates="improvement_suggestions"
    )
