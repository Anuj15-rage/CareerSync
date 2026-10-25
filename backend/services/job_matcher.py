"""
Job Matching Service for CareerSync.

Performs deterministic, explainable skill-weighted matching between a candidate's
verified resume skills and target job roles.
Formula:
    Score = round((sum(matched_weights) / sum(total_role_weights)) * 100, 2)
Guards:
    Zero denominator -> 0.00%
    Unanalyzed resume -> UnanalyzedResumeError (HTTP 400)
    Nonexistent resume/role -> ValueError (HTTP 404)
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import (
    JobRole,
    JobRoleSkill,
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeSkill,
)

logger = logging.getLogger("careersync.services.job_matcher")


class UnanalyzedResumeError(ValueError):
    """Raised when matching is requested on an uploaded resume that has not been analyzed."""
    pass


def compute_single_role_match(
    candidate_skills_map: Dict[int, str],
    role: JobRole,
    role_skills: List[JobRoleSkill],
) -> Dict[str, Any]:
    """
    Compute explainable weighted match score between candidate verified skills
    and a specific job role.
    All scores, counts, and explanations are dynamically computed from database records.
    """
    total_role_weight: float = 0.0
    matched_weight: float = 0.0

    required_weight_total: float = 0.0
    required_weight_matched: float = 0.0

    preferred_weight_total: float = 0.0
    preferred_weight_matched: float = 0.0

    matched_skills: List[Dict[str, Any]] = []
    missing_required_skills: List[Dict[str, Any]] = []
    missing_preferred_skills: List[Dict[str, Any]] = []

    for jrs in role_skills:
        skill_weight = float(jrs.weight)
        importance = jrs.importance
        skill_name = jrs.skill.name if jrs.skill else f"Skill #{jrs.skill_id}"
        skill_cat = jrs.skill.category if jrs.skill else "TECHNICAL"

        total_role_weight += skill_weight

        if importance == "REQUIRED":
            required_weight_total += skill_weight
        elif importance == "PREFERRED":
            preferred_weight_total += skill_weight

        # Check if candidate has this skill
        if jrs.skill_id in candidate_skills_map:
            matched_weight += skill_weight
            extraction_source = candidate_skills_map[jrs.skill_id]

            if importance == "REQUIRED":
                required_weight_matched += skill_weight
            elif importance == "PREFERRED":
                preferred_weight_matched += skill_weight

            matched_skills.append({
                "skill_id": jrs.skill_id,
                "skill_name": skill_name,
                "category": skill_cat,
                "importance": importance,
                "weight": round(skill_weight, 2),
                "extraction_source": extraction_source,
            })
        else:
            missing_item = {
                "skill_id": jrs.skill_id,
                "skill_name": skill_name,
                "category": skill_cat,
                "importance": importance,
                "weight": round(skill_weight, 2),
            }
            if importance == "REQUIRED":
                missing_required_skills.append(missing_item)
            else:
                missing_preferred_skills.append(missing_item)

    # Calculate overall match score (0.00 to 100.00)
    if total_role_weight > 0:
        match_score = round((matched_weight / total_role_weight) * 100, 2)
    else:
        match_score = 0.00

    # Calculate required skills match percentage
    if required_weight_total > 0:
        required_pct = round((required_weight_matched / required_weight_total) * 100, 2)
    else:
        required_pct = 0.00

    # Build dynamic human-readable explanation
    total_skills_count = len(role_skills)
    matched_count = len(matched_skills)
    req_total_count = sum(1 for j in role_skills if j.importance == "REQUIRED")
    req_matched_count = sum(1 for m in matched_skills if m["importance"] == "REQUIRED")
    pref_total_count = sum(1 for j in role_skills if j.importance == "PREFERRED")
    pref_matched_count = sum(1 for m in matched_skills if m["importance"] == "PREFERRED")

    if total_skills_count == 0:
        explanation = f"Role '{role.title}' has no mapped skills in catalog. Match score is 0.00%."
    elif matched_count == 0:
        explanation = f"Matched 0 of {total_skills_count} skills. Score: 0.00 / {total_role_weight:.2f} points (0.00%). Missing {len(missing_required_skills)} required skills."
    elif matched_count == total_skills_count:
        explanation = f"Perfect match! Matched all {total_skills_count} skills ({req_matched_count} Required, {pref_matched_count} Preferred). Score: {matched_weight:.2f} / {total_role_weight:.2f} points (100.00%)."
    else:
        explanation = (
            f"Matched {matched_count} of {total_skills_count} skills "
            f"({req_matched_count} of {req_total_count} Required, {pref_matched_count} of {pref_total_count} Preferred). "
            f"Score: {matched_weight:.2f} / {total_role_weight:.2f} points ({match_score:.2f}%). "
            f"Missing {len(missing_required_skills)} required and {len(missing_preferred_skills)} preferred skills."
        )

    score_breakdown = {
        "total_role_weight": round(total_role_weight, 2),
        "matched_weight": round(matched_weight, 2),
        "required_weight_total": round(required_weight_total, 2),
        "required_weight_matched": round(required_weight_matched, 2),
        "preferred_weight_total": round(preferred_weight_total, 2),
        "preferred_weight_matched": round(preferred_weight_matched, 2),
        "formula": "(matched_weight / total_role_weight) * 100",
    }

    return {
        "job_role_id": role.id,
        "job_role_title": role.title,
        "domain": role.domain,
        "experience_level": role.experience_level,
        "match_score": match_score,
        "matched_skills_count": matched_count,
        "total_role_skills_count": total_skills_count,
        "required_skills_match_percentage": required_pct,
        "matched_skills": matched_skills,
        "missing_required_skills": missing_required_skills,
        "missing_preferred_skills": missing_preferred_skills,
        "score_breakdown": score_breakdown,
        "explanation": explanation,
    }


def match_resume_to_roles(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve candidate verified skills and evaluate against active job roles.
    Distinguishes unparsed / unanalyzed resumes from analyzed resumes with 0 recognized skills.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.parsing_status != "PARSED" or not resume.raw_text:
        raise ValueError(
            f"Resume {resume_id} has parsing status '{resume.parsing_status}' and has not been successfully parsed."
        )

    # Check whether the resume has completed analysis
    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    # Fetch candidate verified skills map {skill_id: extraction_source}
    candidate_skills = db.query(ResumeSkill).filter(ResumeSkill.resume_id == resume_id).all()
    candidate_skills_map = {rs.skill_id: rs.extraction_source for rs in candidate_skills}

    # Fetch target job role(s)
    if target_role_id is not None:
        role = db.query(JobRole).filter(JobRole.id == target_role_id, JobRole.is_active == True).first()
        if not role:
            raise ValueError(f"Job role with ID {target_role_id} not found or inactive.")
        roles = [role]
    else:
        roles = db.query(JobRole).filter(JobRole.is_active == True).all()

    matches: List[Dict[str, Any]] = []
    for role in roles:
        role_skills = (
            db.query(JobRoleSkill)
            .filter(JobRoleSkill.job_role_id == role.id)
            .all()
        )
        match_res = compute_single_role_match(candidate_skills_map, role, role_skills)
        matches.append(match_res)

    # Sort matches by match_score descending, then required_skills_match_percentage descending
    matches.sort(
        key=lambda m: (m["match_score"], m["required_skills_match_percentage"]),
        reverse=True,
    )

    logger.info(
        "Job matching computed for resume %s: %s candidate skills, %s roles evaluated",
        resume_id,
        len(candidate_skills_map),
        len(matches),
    )

    return {
        "resume_id": resume.id,
        "candidate_name": resume.candidate_name,
        "total_candidate_skills": len(candidate_skills_map),
        "matched_roles_count": len(matches),
        "matches": matches,
        "evaluated_at": datetime.now(),
    }
