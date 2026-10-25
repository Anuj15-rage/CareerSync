import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeSkill,
    Skill,
)
from backend.schemas.analysis import (
    CandidateInfo,
    ExtractedEducationItem,
    ExtractedExperienceItem,
    ExtractedProjectItem,
    ExtractedSkillItem,
    ResumeAnalysisResponse,
)
from backend.schemas.matching import (
    JobRoleMatchScore,
    MatchedSkillDetail,
    MissingSkillDetail,
    ResumeJobMatchingResponse,
)
from backend.schemas.recommendation import (
    CareerRecommendationItem,
    CertificationRecommendationItem,
    ResourceRecommendationItem,
    ResumeCareerRecommendationsResponse,
    ResumeCertificationsResponse,
    ResumeConsolidatedRecommendationsResponse,
    ResumeLearningResourcesResponse,
    RoleCertificationsResponse,
    RoleConsolidatedRecommendations,
    RoleLearningResourcesResponse,
)
from backend.schemas.resume import ResumeMetadataResponse, ResumeUploadResponse
from backend.schemas.skill_gap import (
    ResumeSkillGapsResponse,
    RoleSkillGapDetail,
)
from backend.services.career_recommender import (
    generate_and_persist_career_recommendations,
    get_persisted_career_recommendations,
)
from backend.services.resource_recommender import (
    generate_and_persist_resource_recommendations,
    get_persisted_certifications,
    get_persisted_consolidated_recommendations,
    get_persisted_learning_resources,
)
from backend.services.job_matcher import (
    UnanalyzedResumeError,
    match_resume_to_roles,
)
from backend.services.resume_analyzer import analyze_resume_transactional
from backend.services.skill_gap_analyzer import (
    analyze_and_persist_skill_gaps,
    get_persisted_skill_gaps,
)
from backend.services.security import (
    generate_access_token,
    hash_access_token,
    remove_resume_token_hash,
    store_resume_token_hash,
    verify_resume_access,
)
from backend.services.resume_extractor import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    compute_file_hash,
    extract_text_from_docx,
    extract_text_from_pdf,
    sanitize_filename,
    validate_file_signature,
)
from backend.services.rate_limiter import check_upload_rate_limit
from backend.services.cleanup import trigger_lazy_cleanup

logger = logging.getLogger("careersync.api.resumes")

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and extract text from a resume (PDF/DOCX)",
    dependencies=[Depends(check_upload_rate_limit)],
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume document in PDF or DOCX format"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Accepts PDF or DOCX resume uploads (up to 5 MB).
    Validates file extension, magic signature, and extracts readable text.
    Stores resume metadata and extracted text safely in MySQL.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Only PDF and DOCX files are allowed.",
        )

    # Read binary content in bounded chunks to prevent memory exhaustion on oversized payloads
    CHUNK_SIZE = 64 * 1024  # 64 KB per chunk
    chunks = []
    file_size = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds the 5 MB limit ({file_size} bytes).",
            )
        chunks.append(chunk)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    content = b"".join(chunks)

    # Validate actual magic signature
    if not validate_file_signature(content, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File signature mismatch. The file content does not match the '{ext}' format.",
        )

    sanitized_name = sanitize_filename(file.filename)
    file_type = ext.lstrip(".").upper()
    file_hash = compute_file_hash(content)

    # Extract text based on file format
    if file_type == "PDF":
        extracted_text, success, message = extract_text_from_pdf(content)
    elif file_type == "DOCX":
        extracted_text, success, message = extract_text_from_docx(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_type}",
        )

    parsing_status = "PARSED" if success else "FAILED"
    stored_text = extracted_text if success else None

    # Calculate text statistics
    char_count = len(extracted_text) if extracted_text else 0
    word_count = len(extracted_text.split()) if extracted_text else 0

    try:
        raw_token = generate_access_token()
        token_hash = hash_access_token(raw_token)

        resume = Resume(
            file_name=sanitized_name,
            file_type=file_type,
            file_size_bytes=file_size,
            file_hash=file_hash,
            raw_text=stored_text,
            parsing_status=parsing_status,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        store_resume_token_hash(resume.id, token_hash, db)

        logger.info(
            "Resume saved successfully: id=%s, file_name='%s', status=%s, words=%s",
            resume.id,
            sanitized_name,
            parsing_status,
            word_count,
        )

        if background_tasks:
            background_tasks.add_task(trigger_lazy_cleanup)

        return ResumeUploadResponse(
            id=resume.id,
            file_name=resume.file_name,
            file_type=resume.file_type,
            file_size_bytes=resume.file_size_bytes,
            file_hash=resume.file_hash,
            parsing_status=resume.parsing_status,
            character_count=char_count,
            word_count=word_count,
            message=message,
            created_at=resume.created_at,
            access_token=raw_token,
        )

    except SQLAlchemyError as sae:
        db.rollback()
        logger.error("Database error while saving resume: %s", sae)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while saving the resume metadata.",
        )


@router.get(
    "/{resume_id}",
    response_model=ResumeMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get resume metadata and text statistics (excludes raw text)",
    dependencies=[Depends(verify_resume_access)],
)
def get_resume_metadata(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve resume file metadata and text length statistics.
    Strictly excludes raw_text, candidate personal info, and contact details.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found.",
        )

    raw = resume.raw_text or ""
    char_count = len(raw)
    word_count = len(raw.split())

    return ResumeMetadataResponse(
        id=resume.id,
        file_name=resume.file_name,
        file_type=resume.file_type,
        file_size_bytes=resume.file_size_bytes,
        file_hash=resume.file_hash,
        parsing_status=resume.parsing_status,
        character_count=char_count,
        word_count=word_count,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


@router.post(
    "/{resume_id}/analyze",
    response_model=ResumeAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze extracted resume text and populate normalized tables",
    dependencies=[Depends(verify_resume_access)],
)
def analyze_resume(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Parses resume text to extract skills matching catalog skills,
    education, projects, work experience, and contact details.
    Persists results transactionally into normalized child tables.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found.",
        )

    if resume.parsing_status != "PARSED" or not resume.raw_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resume {resume_id} has parsing status '{resume.parsing_status}' and cannot be analyzed.",
        )

    try:
        result = analyze_resume_transactional(resume_id=resume_id, db=db)
        return ResumeAnalysisResponse(
            resume_id=result["resume_id"],
            candidate=CandidateInfo(**result["candidate"]),
            skills=[ExtractedSkillItem(**s) for s in result["skills"]],
            education=[ExtractedEducationItem(**e) for e in result["education"]],
            projects=[ExtractedProjectItem(**p) for p in result["projects"]],
            experience=[ExtractedExperienceItem(**x) for x in result["experience"]],
            unmatched_skills=result.get("unmatched_skills", []),
            message=result["message"],
            analyzed_at=result.get("analysis_completed_at")
            or resume.analysis_completed_at
            or datetime.now(),
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error("Error analyzing resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing the resume.",
        )


@router.get(
    "/{resume_id}/analysis",
    response_model=ResumeAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve previously analyzed resume entities",
    dependencies=[Depends(verify_resume_access)],
)
def get_resume_analysis(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve stored analysis records (skills, education, projects, experience, contact details)
    for a previously analyzed resume.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found.",
        )

    if resume.analysis_completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first.",
        )

    # Query child records
    skills_records = (
        db.query(ResumeSkill)
        .filter(ResumeSkill.resume_id == resume_id)
        .all()
    )
    education_records = (
        db.query(ResumeEducation)
        .filter(ResumeEducation.resume_id == resume_id)
        .all()
    )
    project_records = (
        db.query(ResumeProject)
        .filter(ResumeProject.resume_id == resume_id)
        .all()
    )
    experience_records = (
        db.query(ResumeExperience)
        .filter(ResumeExperience.resume_id == resume_id)
        .all()
    )

    # Join skill names from catalog
    extracted_skills: List[ExtractedSkillItem] = []
    for rs in skills_records:
        skill_obj = db.query(Skill).filter(Skill.id == rs.skill_id).first()
        if skill_obj:
            extracted_skills.append(
                ExtractedSkillItem(
                    skill_id=rs.skill_id,
                    skill_name=skill_obj.name,
                    category=skill_obj.category,
                    extraction_source=rs.extraction_source,
                )
            )

    extracted_education = [
        ExtractedEducationItem(
            id=e.id,
            institution=e.institution,
            degree=e.degree,
            field_of_study=e.field_of_study,
            start_year=e.start_year,
            end_year=e.end_year,
            grade_or_cgpa=e.grade_or_cgpa,
        )
        for e in education_records
    ]

    extracted_projects = [
        ExtractedProjectItem(
            id=p.id,
            title=p.title,
            description=p.description,
            technologies_used=p.technologies_used,
        )
        for p in project_records
    ]

    extracted_experience = [
        ExtractedExperienceItem(
            id=x.id,
            organization=x.organization,
            role_title=x.role_title,
            duration=x.duration,
            description=x.description,
        )
        for x in experience_records
    ]

    candidate_info = CandidateInfo(
        candidate_name=resume.candidate_name,
        candidate_email=resume.candidate_email,
        candidate_phone=resume.candidate_phone,
    )

    return ResumeAnalysisResponse(
        resume_id=resume.id,
        candidate=candidate_info,
        skills=extracted_skills,
        education=extracted_education,
        projects=extracted_projects,
        experience=extracted_experience,
        unmatched_skills=[],
        message=f"Retrieved analysis: {len(extracted_skills)} skills, {len(extracted_education)} education, {len(extracted_projects)} projects, {len(extracted_experience)} experience.",
        analyzed_at=resume.analysis_completed_at,
    )


@router.get(
    "/{resume_id}/matches",
    response_model=ResumeJobMatchingResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate explainable match scores against all active job roles",
    dependencies=[Depends(verify_resume_access)],
)
def get_job_role_matches(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluates the candidate's verified skills against all active catalog job roles.
    Calculates deterministic, weighted skill-coverage match scores.
    """
    try:
        result = match_resume_to_roles(resume_id=resume_id, db=db)
        return ResumeJobMatchingResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error computing matches for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while computing job matches.",
        )


@router.get(
    "/{resume_id}/matches/{job_role_id}",
    response_model=ResumeJobMatchingResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate explainable match score against a specific job role",
    dependencies=[Depends(verify_resume_access)],
)
def get_single_job_role_match(
    resume_id: int,
    job_role_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluates the candidate's verified skills against a single specified job role.
    """
    try:
        result = match_resume_to_roles(
            resume_id=resume_id, db=db, target_role_id=job_role_id
        )
        return ResumeJobMatchingResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(
            "Error computing match for resume %s and role %s: %s",
            resume_id,
            job_role_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while computing job match.",
        )


@router.post(
    "/{resume_id}/skill-gaps/analyze",
    response_model=ResumeSkillGapsResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze and persist candidate skill gaps against all active job roles",
    dependencies=[Depends(verify_resume_access)],
)
def analyze_skill_gaps(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluates candidate verified skills against active catalog job roles.
    Persists evaluation sessions to analysis_sessions and missing skills to skill_gaps.
    Idempotent: updates existing sessions and refreshes gaps without creating duplicates.
    """
    try:
        result = analyze_and_persist_skill_gaps(resume_id=resume_id, db=db)
        return ResumeSkillGapsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error analyzing skill gaps for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while analyzing skill gaps.",
        )


@router.get(
    "/{resume_id}/skill-gaps",
    response_model=ResumeSkillGapsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted skill gaps across all active job roles",
    dependencies=[Depends(verify_resume_access)],
)
def get_skill_gaps(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of previously persisted skill gaps.
    Does NOT compute or trigger writes to the database.
    """
    try:
        result = get_persisted_skill_gaps(resume_id=resume_id, db=db)
        return ResumeSkillGapsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been performed" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error retrieving skill gaps for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving skill gaps.",
        )


@router.get(
    "/{resume_id}/skill-gaps/{job_role_id}",
    response_model=RoleSkillGapDetail,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted skill gaps for a specific job role",
    dependencies=[Depends(verify_resume_access)],
)
def get_single_role_skill_gaps(
    resume_id: int,
    job_role_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of previously persisted skill gaps for a specific job role.
    """
    try:
        result = get_persisted_skill_gaps(
            resume_id=resume_id, db=db, target_role_id=job_role_id
        )
        if not result["role_gaps"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No skill gap analysis found for resume {resume_id} and role {job_role_id}.",
            )
        return RoleSkillGapDetail(**result["role_gaps"][0])
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been performed" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(
            "Error retrieving skill gaps for resume %s and role %s: %s",
            resume_id,
            job_role_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving skill gaps.",
        )


@router.post(
    "/{resume_id}/career-recommendations/analyze",
    response_model=ResumeCareerRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and persist deterministic career recommendations",
    dependencies=[Depends(verify_resume_access)],
)
def analyze_career_recommendations(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluates candidate verified skills, integrates Stage 5.1 weighted scoring and
    Stage 5.2 skill gaps, and generates explainable career recommendations persisted
    in the career_recommendations table.
    Idempotent: updates existing recommendations without creating duplicates.
    """
    try:
        result = generate_and_persist_career_recommendations(resume_id=resume_id, db=db)
        return ResumeCareerRecommendationsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error generating career recommendations for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating career recommendations.",
        )


@router.get(
    "/{resume_id}/career-recommendations",
    response_model=ResumeCareerRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted career recommendations",
    dependencies=[Depends(verify_resume_access)],
)
def get_career_recommendations(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of previously persisted career recommendations.
    Does NOT compute or trigger writes to the database.
    """
    try:
        result = get_persisted_career_recommendations(resume_id=resume_id, db=db)
        return ResumeCareerRecommendationsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error retrieving career recommendations for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving career recommendations.",
        )


@router.get(
    "/{resume_id}/career-recommendations/{job_role_id}",
    response_model=CareerRecommendationItem,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted career recommendation for a specific job role",
    dependencies=[Depends(verify_resume_access)],
)
def get_single_role_career_recommendation(
    resume_id: int,
    job_role_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of a previously persisted career recommendation for a specific job role.
    """
    try:
        result = get_persisted_career_recommendations(
            resume_id=resume_id, db=db, target_role_id=job_role_id
        )
        if not result["recommendations"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No career recommendation found for resume {resume_id} and role {job_role_id}.",
            )
        return CareerRecommendationItem(**result["recommendations"][0])
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(
            "Error retrieving career recommendation for resume %s and role %s: %s",
            resume_id,
            job_role_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving career recommendation.",
        )


@router.post(
    "/{resume_id}/resource-recommendations/analyze",
    response_model=ResumeConsolidatedRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and persist learning resource and certification recommendations",
    dependencies=[Depends(verify_resume_access)],
)
def analyze_resource_recommendations(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluates candidate skill gaps, maps them to vetted learning resources and
    industry certifications, and transactionally persists recommendations.
    Idempotent: updates recommendations for the exact sessions without creating duplicates.
    """
    try:
        result = generate_and_persist_resource_recommendations(resume_id=resume_id, db=db)
        return ResumeConsolidatedRecommendationsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error generating resource recommendations for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating resource recommendations.",
        )


@router.get(
    "/{resume_id}/learning-resources",
    response_model=ResumeLearningResourcesResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted learning resource recommendations across all active roles",
    dependencies=[Depends(verify_resume_access)],
)
def get_learning_resources(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of persisted learning resource recommendations.
    Does NOT compute or trigger writes to the database.
    """
    try:
        result = get_persisted_learning_resources(resume_id=resume_id, db=db)
        return ResumeLearningResourcesResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error retrieving learning resources for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving learning resources.",
        )


@router.get(
    "/{resume_id}/learning-resources/{job_role_id}",
    response_model=RoleLearningResourcesResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted learning resource recommendations for a specific job role",
    dependencies=[Depends(verify_resume_access)],
)
def get_single_role_learning_resources(
    resume_id: int,
    job_role_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of persisted learning resources for a specific job role.
    """
    try:
        result = get_persisted_learning_resources(
            resume_id=resume_id, db=db, target_role_id=job_role_id
        )
        if not result["roles"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No learning resources found for resume {resume_id} and role {job_role_id}.",
            )
        return RoleLearningResourcesResponse(**result["roles"][0])
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(
            "Error retrieving learning resources for resume %s and role %s: %s",
            resume_id,
            job_role_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving learning resources.",
        )


@router.get(
    "/{resume_id}/certifications",
    response_model=ResumeCertificationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted certification recommendations across all active roles",
    dependencies=[Depends(verify_resume_access)],
)
def get_certifications(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of persisted certification recommendations.
    Does NOT compute or trigger writes to the database.
    """
    try:
        result = get_persisted_certifications(resume_id=resume_id, db=db)
        return ResumeCertificationsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error retrieving certifications for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving certifications.",
        )


@router.get(
    "/{resume_id}/certifications/{job_role_id}",
    response_model=RoleCertificationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted certification recommendations for a specific job role",
    dependencies=[Depends(verify_resume_access)],
)
def get_single_role_certifications(
    resume_id: int,
    job_role_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of persisted certifications for a specific job role.
    """
    try:
        result = get_persisted_certifications(
            resume_id=resume_id, db=db, target_role_id=job_role_id
        )
        if not result["roles"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No certifications found for resume {resume_id} and role {job_role_id}.",
            )
        return RoleCertificationsResponse(**result["roles"][0])
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(
            "Error retrieving certifications for resume %s and role %s: %s",
            resume_id,
            job_role_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving certifications.",
        )


@router.get(
    "/{resume_id}/resource-recommendations",
    response_model=ResumeConsolidatedRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve consolidated recommendations (resources + certs) across all active roles",
    dependencies=[Depends(verify_resume_access)],
)
def get_resource_recommendations(
    resume_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of consolidated recommendations.
    Does NOT compute or trigger writes to the database.
    """
    try:
        result = get_persisted_consolidated_recommendations(resume_id=resume_id, db=db)
        return ResumeConsolidatedRecommendationsResponse(**result)
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error("Error retrieving resource recommendations for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving resource recommendations.",
        )


@router.get(
    "/{resume_id}/resource-recommendations/{job_role_id}",
    response_model=RoleConsolidatedRecommendations,
    status_code=status.HTTP_200_OK,
    summary="Retrieve consolidated recommendations for a specific job role",
    dependencies=[Depends(verify_resume_access)],
)
def get_single_role_resource_recommendations(
    resume_id: int,
    job_role_id: int,
    db: Session = Depends(get_db),
):
    """
    Strictly read-only retrieval of consolidated recommendations for a specific job role.
    """
    try:
        result = get_persisted_consolidated_recommendations(
            resume_id=resume_id, db=db, target_role_id=job_role_id
        )
        if not result["roles"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No recommendations found for resume {resume_id} and role {job_role_id}.",
            )
        return RoleConsolidatedRecommendations(**result["roles"][0])
    except UnanalyzedResumeError as ure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ure),
        )
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower() or "not been generated" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(
            "Error retrieving resource recommendations for resume %s and role %s: %s",
            resume_id,
            job_role_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving resource recommendations.",
        )







@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_200_OK,
    summary="Permanently delete an uploaded resume and all associated analysis data",
    dependencies=[Depends(verify_resume_access)],
)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    resume: Resume = Depends(verify_resume_access),
):
    """
    Permanently deletes the specified resume record and all child data
    (skills, sections, analysis sessions, recommendations, matches).
    Guarantees master catalog tables (job roles, skills, learning resources) remain untouched.
    Requires valid X-Resume-Token matching the resume's access_token_hash.
    """
    try:
        db.delete(resume)
        db.commit()
        remove_resume_token_hash(resume_id)
        logger.info("Resume %s and all associated data permanently deleted.", resume_id)
        return {
            "success": True,
            "message": f"Resume {resume_id} and all associated analysis data have been permanently deleted.",
        }
    except SQLAlchemyError as sae:
        db.rollback()
        logger.error("Database error while deleting resume %s: %s", resume_id, sae)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resume due to a database error.",
        )
