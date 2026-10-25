"""
Stage 5.2 — Skill Gap Analyzer Service
Deterministic, database-driven skill gap analysis linking candidate verified skills
to target job roles using analysis_sessions and skill_gaps tables.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    AnalysisSession,
    JobRole,
    JobRoleSkill,
    Resume,
    ResumeSkill,
    Skill,
    SkillGap,
)
from backend.services.job_matcher import (
    UnanalyzedResumeError,
    compute_single_role_match,
)

logger = logging.getLogger("careersync.services.skill_gap_analyzer")


def analyze_and_persist_skill_gaps(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Evaluates candidate verified skills against active job roles,
    transactionally persists analysis_sessions and skill_gaps, and returns
    the structured gap analysis.

    Guarantees:
    - Validates resume exists and resume.analysis_completed_at is not None.
    - Does NOT modify resume.analysis_completed_at.
    - Idempotent: re-running updates existing sessions and refreshes child skill_gaps.
    - Clean transactional rollback on failure.
    - Supports zero recognized skills and 100% perfect matches.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    # Fetch candidate verified skills {skill_id: extraction_source}
    cand_skills = db.query(ResumeSkill).filter(ResumeSkill.resume_id == resume_id).all()
    candidate_skills_map = {rs.skill_id: rs.extraction_source for rs in cand_skills}

    # Fetch target job role(s)
    if target_role_id is not None:
        role = db.query(JobRole).filter(JobRole.id == target_role_id, JobRole.is_active == True).first()
        if not role:
            raise ValueError(f"Job role with ID {target_role_id} not found or inactive.")
        roles = [role]
    else:
        roles = db.query(JobRole).filter(JobRole.is_active == True).all()

    role_gap_results: List[Dict[str, Any]] = []

    try:
        for role in roles:
            # Re-use deterministic single-role matching from Stage 5.1
            match_res = compute_single_role_match(
                candidate_skills_map=candidate_skills_map,
                role=role,
                role_skills=role.skill_associations,
            )

            comp_score = match_res["match_score"]
            tech_score = match_res["required_skills_match_percentage"]
            explanation = match_res["explanation"]

            # Locate existing session specifically for this (resume_id, job_role_id)
            session = (
                db.query(AnalysisSession)
                .filter(
                    AnalysisSession.resume_id == resume_id,
                    AnalysisSession.job_role_id == role.id,
                )
                .first()
            )

            if session:
                # Atomically delete previous skill gaps for this specific session only
                db.query(SkillGap).filter(SkillGap.session_id == session.id).delete(synchronize_session=False)
                session.target_role_title = role.title
                session.target_job_description = role.overview
                session.compatibility_score = comp_score
                session.technical_skill_score = tech_score
                session.methodology_notes = explanation
                session.created_at = func.now()
            else:
                session = AnalysisSession(
                    resume_id=resume_id,
                    job_role_id=role.id,
                    target_role_title=role.title,
                    target_job_description=role.overview,
                    compatibility_score=comp_score,
                    technical_skill_score=tech_score,
                    methodology_notes=explanation,
                )
                db.add(session)
                db.flush()  # Acquire generated session.id for foreign key

            # Map missing REQUIRED skills -> CRITICAL_MISSING
            critical_missing_items: List[Dict[str, Any]] = []
            for req in match_res["missing_required_skills"]:
                reason_text = (
                    f"Critical missing skill: '{req['skill_name']}' (weight: {req['weight']:.2f}) "
                    f"is required for {role.title}."
                )[:255]
                gap = SkillGap(
                    session_id=session.id,
                    skill_id=req["skill_id"],
                    gap_priority="CRITICAL_MISSING",
                    reason=reason_text,
                )
                db.add(gap)
                critical_missing_items.append({
                    "skill_id": req["skill_id"],
                    "skill_name": req["skill_name"],
                    "category": req["category"],
                    "importance": "REQUIRED",
                    "weight": req["weight"],
                    "gap_priority": "CRITICAL_MISSING",
                    "reason": reason_text,
                })

            # Map missing PREFERRED skills -> SECONDARY_MISSING
            secondary_missing_items: List[Dict[str, Any]] = []
            for pref in match_res["missing_preferred_skills"]:
                reason_text = (
                    f"Secondary missing skill: '{pref['skill_name']}' (weight: {pref['weight']:.2f}) "
                    f"is preferred for {role.title}."
                )[:255]
                gap = SkillGap(
                    session_id=session.id,
                    skill_id=pref["skill_id"],
                    gap_priority="SECONDARY_MISSING",
                    reason=reason_text,
                )
                db.add(gap)
                secondary_missing_items.append({
                    "skill_id": pref["skill_id"],
                    "skill_name": pref["skill_name"],
                    "category": pref["category"],
                    "importance": "PREFERRED",
                    "weight": pref["weight"],
                    "gap_priority": "SECONDARY_MISSING",
                    "reason": reason_text,
                })

            # Format possessed skills
            possessed_items = [
                {
                    "skill_id": m["skill_id"],
                    "skill_name": m["skill_name"],
                    "category": m["category"],
                    "importance": m["importance"],
                    "weight": m["weight"],
                    "extraction_source": m.get("extraction_source", "SKILLS_SECTION"),
                }
                for m in match_res["matched_skills"]
            ]

            role_gap_results.append({
                "session_id": session.id,
                "job_role_id": role.id,
                "job_role_title": role.title,
                "domain": role.domain,
                "experience_level": role.experience_level,
                "compatibility_score": comp_score,
                "technical_skill_score": tech_score,
                "total_role_skills_count": match_res["total_role_skills_count"],
                "possessed_skills_count": len(possessed_items),
                "missing_skills_count": len(critical_missing_items) + len(secondary_missing_items),
                "critical_missing_count": len(critical_missing_items),
                "secondary_missing_count": len(secondary_missing_items),
                "possessed_skills": possessed_items,
                "critical_missing_skills": critical_missing_items,
                "secondary_missing_skills": secondary_missing_items,
                "explanation": explanation,
                "created_at": datetime.now(),
            })

        db.commit()

        logger.info(
            "Skill gap analysis committed for resume %s: %s roles evaluated",
            resume_id,
            len(role_gap_results),
        )

    except Exception as e:
        db.rollback()
        logger.error("Skill gap analysis failed for resume %s; rolled back: %s", resume_id, e)
        raise e

    # Sort results by compatibility_score descending, then technical_skill_score descending
    role_gap_results.sort(
        key=lambda r: (r["compatibility_score"], r["technical_skill_score"]),
        reverse=True,
    )

    return {
        "resume_id": resume.id,
        "candidate_name": resume.candidate_name,
        "total_candidate_skills": len(candidate_skills_map),
        "roles_evaluated_count": len(role_gap_results),
        "role_gaps": role_gap_results,
        "analyzed_at": datetime.now(),
    }


def get_persisted_skill_gaps(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Strictly read-only retrieval of previously persisted skill gaps.
    Does NOT trigger computations or writes.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    # Query existing sessions for this resume
    query = db.query(AnalysisSession).filter(AnalysisSession.resume_id == resume_id)
    if target_role_id is not None:
        query = query.filter(AnalysisSession.job_role_id == target_role_id)

    sessions = query.all()
    if not sessions:
        if target_role_id is not None:
            raise ValueError(
                f"Skill gap analysis has not been performed for resume {resume_id} and role {target_role_id}. "
                f"Please call POST /api/resumes/{resume_id}/skill-gaps/analyze first."
            )
        raise ValueError(
            f"Skill gap analysis has not been performed for resume {resume_id}. "
            f"Please call POST /api/resumes/{resume_id}/skill-gaps/analyze first."
        )

    # Load candidate skills map
    cand_skills = db.query(ResumeSkill).filter(ResumeSkill.resume_id == resume_id).all()
    candidate_skills_map = {rs.skill_id: rs.extraction_source for rs in cand_skills}

    role_gap_results: List[Dict[str, Any]] = []

    for session in sessions:
        role = session.job_role
        if not role:
            continue

        role_skills_map = {jrs.skill_id: jrs for jrs in role.skill_associations}

        # Possessed skills: candidate skills that match this role
        possessed_items: List[Dict[str, Any]] = []
        for s_id, source in candidate_skills_map.items():
            if s_id in role_skills_map:
                jrs = role_skills_map[s_id]
                possessed_items.append({
                    "skill_id": s_id,
                    "skill_name": jrs.skill.name if jrs.skill else f"Skill #{s_id}",
                    "category": jrs.skill.category if jrs.skill else "TECHNICAL",
                    "importance": jrs.importance,
                    "weight": round(float(jrs.weight), 2),
                    "extraction_source": source,
                })

        # Missing skills: read from persisted skill_gaps
        critical_missing_items: List[Dict[str, Any]] = []
        secondary_missing_items: List[Dict[str, Any]] = []

        for gap in session.skill_gaps:
            jrs = role_skills_map.get(gap.skill_id)
            skill_name = gap.skill.name if gap.skill else f"Skill #{gap.skill_id}"
            skill_cat = gap.skill.category if gap.skill else "TECHNICAL"
            importance = jrs.importance if jrs else ("REQUIRED" if gap.gap_priority == "CRITICAL_MISSING" else "PREFERRED")
            weight = round(float(jrs.weight), 2) if jrs else (1.00 if gap.gap_priority == "CRITICAL_MISSING" else 0.75)

            item = {
                "skill_id": gap.skill_id,
                "skill_name": skill_name,
                "category": skill_cat,
                "importance": importance,
                "weight": weight,
                "gap_priority": gap.gap_priority,
                "reason": gap.reason or "",
            }

            if gap.gap_priority == "CRITICAL_MISSING":
                critical_missing_items.append(item)
            else:
                secondary_missing_items.append(item)

        comp_score = float(session.compatibility_score) if session.compatibility_score is not None else 0.00
        tech_score = float(session.technical_skill_score) if session.technical_skill_score is not None else 0.00

        role_gap_results.append({
            "session_id": session.id,
            "job_role_id": role.id,
            "job_role_title": session.target_role_title,
            "domain": role.domain,
            "experience_level": role.experience_level,
            "compatibility_score": comp_score,
            "technical_skill_score": tech_score,
            "total_role_skills_count": len(role_skills_map),
            "possessed_skills_count": len(possessed_items),
            "missing_skills_count": len(critical_missing_items) + len(secondary_missing_items),
            "critical_missing_count": len(critical_missing_items),
            "secondary_missing_count": len(secondary_missing_items),
            "possessed_skills": possessed_items,
            "critical_missing_skills": critical_missing_items,
            "secondary_missing_skills": secondary_missing_items,
            "explanation": session.methodology_notes or "",
            "created_at": session.created_at,
        })

    role_gap_results.sort(
        key=lambda r: (r["compatibility_score"], r["technical_skill_score"]),
        reverse=True,
    )

    return {
        "resume_id": resume.id,
        "candidate_name": resume.candidate_name,
        "total_candidate_skills": len(candidate_skills_map),
        "roles_evaluated_count": len(role_gap_results),
        "role_gaps": role_gap_results,
        "analyzed_at": datetime.now(),
    }
