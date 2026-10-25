from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship

from backend.database import Base


class CertificationProvider(Base):
    __tablename__ = "certification_providers"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)
    official_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    certifications = relationship(
        "Certification", back_populates="provider", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CertificationProvider(id={self.id}, name='{self.name}')>"


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    provider_id = Column(
        INTEGER(unsigned=True),
        ForeignKey("certification_providers.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    level = Column(
        Enum("ENTRY", "ASSOCIATE", "PROFESSIONAL", name="cert_level_enum"),
        nullable=False,
        default="ENTRY",
        index=True,
    )
    official_url = Column(String(500), nullable=False)
    overview = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_cert_provider_name"),
    )

    # Relationships
    provider = relationship("CertificationProvider", back_populates="certifications")
    skill_associations = relationship(
        "CertificationSkill", back_populates="certification", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Certification(id={self.id}, name='{self.name}', level='{self.level}')>"


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    title = Column(String(255), unique=True, nullable=False)
    resource_type = Column(
        Enum(
            "DOCUMENTATION",
            "COURSE",
            "TUTORIAL",
            "PRACTICE_PROJECT",
            name="resource_type_enum",
        ),
        nullable=False,
        index=True,
    )
    platform_name = Column(String(100), nullable=False, index=True)
    url = Column(String(500), unique=True, nullable=False)
    is_free = Column(Boolean, nullable=False, default=True)
    difficulty_level = Column(
        Enum("BEGINNER", "INTERMEDIATE", "ADVANCED", name="difficulty_level_enum"),
        nullable=False,
        default="BEGINNER",
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("title", name="uq_resource_title"),
        UniqueConstraint("url", name="uq_resource_url"),
    )

    # Relationships
    skill_associations = relationship(
        "ResourceSkill", back_populates="resource", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LearningResource(id={self.id}, title='{self.title}', platform='{self.platform_name}')>"
