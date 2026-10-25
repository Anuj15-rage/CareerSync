from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship

from backend.database import Base


class JobRole(Base):
    __tablename__ = "job_roles"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    title = Column(String(150), unique=True, nullable=False)
    domain = Column(String(100), nullable=False, index=True)
    overview = Column(Text, nullable=False)
    experience_level = Column(
        Enum("INTERNSHIP", "ENTRY_LEVEL", "JUNIOR", name="role_experience_level_enum"),
        nullable=False,
        default="ENTRY_LEVEL",
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    skill_associations = relationship(
        "JobRoleSkill", back_populates="job_role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JobRole(id={self.id}, title='{self.title}', domain='{self.domain}')>"
