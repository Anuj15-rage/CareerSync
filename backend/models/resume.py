from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT, SMALLINT
from sqlalchemy.orm import relationship

from backend.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    file_size_bytes = Column(INTEGER(unsigned=True), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    raw_text = Column(LONGTEXT, nullable=True)
    candidate_name = Column(String(150), nullable=True)
    candidate_email = Column(String(255), nullable=True)
    candidate_phone = Column(String(50), nullable=True)
    parsing_status = Column(
        Enum("PENDING", "PARSED", "FAILED", name="resume_parsing_status_enum"),
        nullable=False,
        default="PENDING",
        index=True,
    )
    analysis_completed_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    education_entries = relationship(
        "ResumeEducation", back_populates="resume", cascade="all, delete-orphan"
    )
    project_entries = relationship(
        "ResumeProject", back_populates="resume", cascade="all, delete-orphan"
    )
    experience_entries = relationship(
        "ResumeExperience", back_populates="resume", cascade="all, delete-orphan"
    )
    skills = relationship(
        "ResumeSkill", back_populates="resume", cascade="all, delete-orphan"
    )
    analysis_sessions = relationship(
        "AnalysisSession", back_populates="resume", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Resume(id={self.id}, file_name='{self.file_name}', status='{self.parsing_status}')>"


class ResumeEducation(Base):
    __tablename__ = "resume_education"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resume_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("resumes.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    institution = Column(String(255), nullable=True)
    degree = Column(String(150), nullable=True)
    field_of_study = Column(String(150), nullable=True)
    start_year = Column(SMALLINT(unsigned=True), nullable=True)
    end_year = Column(SMALLINT(unsigned=True), nullable=True)
    grade_or_cgpa = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    resume = relationship("Resume", back_populates="education_entries")


class ResumeProject(Base):
    __tablename__ = "resume_projects"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resume_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("resumes.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    technologies_used = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    resume = relationship("Resume", back_populates="project_entries")


class ResumeExperience(Base):
    __tablename__ = "resume_experience"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resume_id = Column(
        BIGINT(unsigned=True),
        ForeignKey("resumes.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    organization = Column(String(255), nullable=True)
    role_title = Column(String(150), nullable=True)
    duration = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    resume = relationship("Resume", back_populates="experience_entries")
