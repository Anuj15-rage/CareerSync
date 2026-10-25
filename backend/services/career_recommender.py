"""
Stage 5.3 — Career Recommendation Service
Deterministic, explainable career recommendations integrating Stage 5.1 weighted scoring
and Stage 5.2 skill gaps, persisted in the existing career_recommendations table.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    AnalysisSession,
    CareerRecommendation,
    JobRole,
    Resume,
    ResumeSkill,
    SkillGap,
)
from backend.services.job_matcher import UnanalyzedResumeError
from backend.services.skill_gap_analyzer import analyze_and_persist_skill_gaps

logger = logging.getLogger("careersync.services.career_recommender")


def determine_fit_level(compatibility_score: float) -> str:
    """Classify match percentage into an explainable, deterministic fit level."""
    if compatibility_score >= 70.0:
        return "STRONG_MATCH"
    elif compatibility_score >= 40.0:
        return "MODERATE_MATCH"
    elif compatibility_score > 0.0:
        return "POTENTIAL_GROWTH"
    else:
        return "NO_MATCH"


def generate_recommendation_rationale(
    role_title: str,
    comp_score: float,
    tech_score: float,
    total_role_skills: int,
    matched_skills: List[str],
    missing_required: List[str],
    missing_preferred: List[str],
) -> str:
    """Generate deterministic, evidence-based recommendation rationale."""
    fit_level = determine_fit_level(comp_score)

    if fit_level == "STRONG_MATCH":
        assessment = f"Strong Fit ({comp_score:.2f}%) — Candidate demonstrates comprehensive alignment with core requirements for {role_title}."
    elif fit_level == "MODERATE_MATCH":
        assessment = f"Moderate Fit ({comp_score:.2f}%) — Candidate demonstrates solid foundational competencies, with clear upskilling targets for {role_title}."
    elif fit_level == "POTENTIAL_GROWTH":
        assessment = f"Growth Path ({comp_score:.2f}%) — Candidate possesses emerging skill overlap; focused training required for role readiness as {role_title}."
    else:
        assessment = f"No Overlap ({comp_score:.2f}%) — None of the candidate's verified skills match the current requirements for {role_title}."

    matched_str = ", ".join(matched_skills) if matched_skills else "None"
    req_missing_str = ", ".join(missing_required) if missing_required else "None"
    pref_missing_str = ", ".join(missing_preferred) if missing_preferred else "None"

    return (
        f"{assessment} "
        f"Compatibility Score: {comp_score:.2f}%. Required Skills Coverage: {tech_score:.2f}%. "
        f"Possesses {len(matched_skills)}/{total_role_skills} skills ({matched_str}). "
        f"Critical Gaps ({len(missing_required)} required): {req_missing_str}. "
        f"Secondary Gaps ({len(missing_preferred)} preferred): {pref_missing_str}."
    )


def generate_and_persist_career_recommendations(
    resume_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Generate and persist deterministic career recommendations for a candidate resume.
    Guarantees:
    - Validates resume exists and resume.analysis_completed_at is not None.
    - Reuses Stage 5.1 and 5.2 data structures and session persistence.
    - Idempotent: updates existing career_recommendations in place without duplicates.
    - Safe rollback on error.
    - Does not modify resume.analysis_completed_at.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    # Ensure AnalysisSession and SkillGap records are up to date for all active roles
    analyze_and_persist_skill_gaps(resume_id=resume_id, db=db)

    # Load active roles
    active_roles = db.query(JobRole).filter(JobRole.is_active == True).all()

    # Load candidate verified skills
    cand_skills = db.query(ResumeSkill).filter(ResumeSkill.resume_id == resume_id).all()
    cand_skill_ids = {rs.skill_id for rs in cand_skills}

    try:
        for role in active_roles:
            session = (
                db.query(AnalysisSession)
                .filter(
                    AnalysisSession.resume_id == resume_id,
                    AnalysisSession.job_role_id == role.id,
                )
                .first()
            )
            if not session:
                continue

            comp_score = float(session.compatibility_score) if session.compatibility_score is not None else 0.00
            tech_score = float(session.technical_skill_score) if session.technical_skill_score is not None else 0.00

            # Gather matched and missing skills
            matched_skills = [
                jrs.skill.name for jrs in role.skill_associations
                if jrs.skill_id in cand_skill_ids and jrs.skill
            ]
            missing_required = [
                gap.skill.name for gap in session.skill_gaps
                if gap.gap_priority == "CRITICAL_MISSING" and gap.skill
            ]
            missing_preferred = [
                gap.skill.name for gap in session.skill_gaps
                if gap.gap_priority == "SECONDARY_MISSING" and gap.skill
            ]

            rationale = generate_recommendation_rationale(
                role_title=role.title,
                comp_score=comp_score,
                tech_score=tech_score,
                total_role_skills=len(role.skill_associations),
                matched_skills=matched_skills,
                missing_required=missing_required,
                missing_preferred=missing_preferred,
            )

            # Check if recommendation already exists for this session and role
            rec = (
                db.query(CareerRecommendation)
                .filter(
                    CareerRecommendation.session_id == session.id,
                    CareerRecommendation.job_role_id == role.id,
                )
                .first()
            )

            if rec:
                rec.match_percentage = comp_score
                rec.rationale = rationale
                rec.created_at = func.now()
            else:
                rec = CareerRecommendation(
                    session_id=session.id,
                    job_role_id=role.id,
                    match_percentage=comp_score,
                    rationale=rationale,
                )
                db.add(rec)

        db.commit()
        logger.info("Career recommendations persisted for resume %s", resume_id)

    except Exception as e:
        db.rollback()
        logger.error("Failed to generate career recommendations for resume %s: %s", resume_id, e)
        raise e

    # Retrieve all persisted recommendations for this resume and format response
    return get_persisted_career_recommendations(resume_id=resume_id, db=db)


def get_persisted_career_recommendations(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Strictly read-only retrieval of persisted career recommendations.
    Does NOT trigger computations or database writes.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    # Fetch all recommendations for this resume
    all_recs = (
        db.query(CareerRecommendation)
        .join(AnalysisSession, CareerRecommendation.session_id == AnalysisSession.id)
        .filter(AnalysisSession.resume_id == resume_id)
        .all()
    )

    if not all_recs:
        if target_role_id is not None:
            raise ValueError(
                f"Career recommendations have not been generated for resume {resume_id} and role {target_role_id}. "
                f"Please call POST /api/resumes/{resume_id}/career-recommendations/analyze first."
            )
        raise ValueError(
            f"Career recommendations have not been generated for resume {resume_id}. "
            f"Please call POST /api/resumes/{resume_id}/career-recommendations/analyze first."
        )

    # Candidate skills
    cand_skills = db.query(ResumeSkill).filter(ResumeSkill.resume_id == resume_id).all()
    cand_skill_ids = {rs.skill_id for rs in cand_skills}

    # Sort all recommendations by match_percentage descending, then role_id ascending
    sorted_recs = sorted(
        all_recs,
        key=lambda r: (
            float(r.match_percentage),
            float(r.session.technical_skill_score or 0.0),
            -r.job_role_id
        ),
        reverse=True,
    )

    formatted_items: List[Dict[str, Any]] = []
    for rank_idx, rec in enumerate(sorted_recs, start=1):
        role = rec.job_role
        session = rec.session
        comp_score = float(rec.match_percentage)
        tech_score = float(session.technical_skill_score) if session and session.technical_skill_score is not None else 0.00

        matched_skills = [
            jrs.skill.name for jrs in role.skill_associations
            if jrs.skill_id in cand_skill_ids and jrs.skill
        ] if role else []

        missing_required = [
            gap.skill.name for gap in session.skill_gaps
            if gap.gap_priority == "CRITICAL_MISSING" and gap.skill
        ] if session else []

        missing_preferred = [
            gap.skill.name for gap in session.skill_gaps
            if gap.gap_priority == "SECONDARY_MISSING" and gap.skill
        ] if session else []

        item = {
            "recommendation_id": rec.id,
            "session_id": rec.session_id,
            "job_role_id": rec.job_role_id,
            "job_role_title": role.title if role else f"Role #{rec.job_role_id}",
            "domain": role.domain if role else "GENERAL",
            "experience_level": role.experience_level if role else "ENTRY_LEVEL",
            "match_percentage": comp_score,
            "technical_skill_score": tech_score,
            "rank": rank_idx,
            "fit_level": determine_fit_level(comp_score),
            "rationale": rec.rationale,
            "matched_skills_count": len(matched_skills),
            "missing_required_count": len(missing_required),
            "missing_preferred_count": len(missing_preferred),
            "matched_skills": matched_skills,
            "missing_required_skills": missing_required,
            "missing_preferred_skills": missing_preferred,
            "created_at": rec.created_at,
        }
        formatted_items.append(item)

    # Filter to specific role if requested
    if target_role_id is not None:
        target_item = next((item for item in formatted_items if item["job_role_id"] == target_role_id), None)
        if not target_item:
            raise ValueError(
                f"No career recommendation found for resume {resume_id} and role {target_role_id}."
            )
        formatted_items = [target_item]

    top_title = formatted_items[0]["job_role_title"] if formatted_items else None

    return {
        "resume_id": resume.id,
        "candidate_name": resume.candidate_name,
        "total_candidate_skills": len(cand_skill_ids),
        "total_recommendations": len(formatted_items),
        "top_recommendation": top_title,
        "recommendations": formatted_items,
        "generated_at": datetime.now(),
    }
