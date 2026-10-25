from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import relationship

from backend.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    normalized_name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(
        Enum(
            "PROGRAMMING_LANGUAGE",
            "FRAMEWORK_LIBRARY",
            "DATABASE",
            "TOOL_PLATFORM",
            "CLOUD_DEVOPS",
            "CORE_CONCEPT",
            "SOFT_SKILL",
            name="skill_category_enum",
        ),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    resume_associations = relationship(
        "ResumeSkill", back_populates="skill", cascade="all, delete-orphan"
    )
    job_role_associations = relationship(
        "JobRoleSkill", back_populates="skill", cascade="all, delete-orphan"
    )
    resource_associations = relationship(
        "ResourceSkill", back_populates="skill", cascade="all, delete-orphan"
    )
    certification_associations = relationship(
        "CertificationSkill", back_populates="skill", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}', category='{self.category}')>"


class ResumeSkill(Base):
    __tablename__ = "resume_skills"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resume_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("resumes.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("skills.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_source = Column(
        Enum(
            "SKILLS_SECTION",
            "PROJECTS",
            "EXPERIENCE",
            "EDUCATION",
            name="resume_skill_source_enum",
        ),
        nullable=False,
        default="SKILLS_SECTION",
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("resume_id", "skill_id", name="uq_resume_skill"),
    )

    # Relationships
    resume = relationship("Resume", back_populates="skills")
    skill = relationship("Skill", back_populates="resume_associations")


class JobRoleSkill(Base):
    __tablename__ = "job_role_skills"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    job_role_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("job_roles.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("skills.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    importance = Column(
        Enum("REQUIRED", "PREFERRED", "NICE_TO_HAVE", name="job_skill_importance_enum"),
        nullable=False,
        default="REQUIRED",
    )
    weight = Column(Numeric(3, 2), nullable=False, default=1.00)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("job_role_id", "skill_id", name="uq_role_skill"),
        CheckConstraint("weight >= 0.00 AND weight <= 1.00", name="chk_role_skill_weight"),
    )

    # Relationships
    job_role = relationship("JobRole", back_populates="skill_associations")
    skill = relationship("Skill", back_populates="job_role_associations")


class ResourceSkill(Base):
    __tablename__ = "resource_skills"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    resource_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("learning_resources.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("skills.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("resource_id", "skill_id", name="uq_resource_skill"),
    )

    # Relationships
    resource = relationship("LearningResource", back_populates="skill_associations")
    skill = relationship("Skill", back_populates="resource_associations")


class CertificationSkill(Base):
    __tablename__ = "certification_skills"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    certification_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("certifications.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("skills.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("certification_id", "skill_id", name="uq_cert_skill"),
    )

    # Relationships
    certification = relationship("Certification", back_populates="skill_associations")
    skill = relationship("Skill", back_populates="certification_associations")
