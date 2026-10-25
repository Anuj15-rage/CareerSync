from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ResumeUploadResponse(BaseModel):
    """Response returned upon resume upload and text extraction."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_type: str
    file_size_bytes: int
    file_hash: str
    parsing_status: str
    character_count: int
    word_count: int
    message: str
    created_at: datetime
    access_token: Optional[str] = None


class ResumeMetadataResponse(BaseModel):
    """
    Safe read-only response for resume inspection.
    Includes file metadata and text statistics ONLY.
    Strictly excludes raw_text, candidate_name, candidate_email, and candidate_phone.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_type: str
    file_size_bytes: int
    file_hash: str
    parsing_status: str
    character_count: int
    word_count: int
    created_at: datetime
    updated_at: datetime
