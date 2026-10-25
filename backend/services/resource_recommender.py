"""
Stage 5.4 — Learning Resource & Certification Recommendation Service
Deterministic recommendations targeting verified skill gaps using existing database tables:
learning_resources, resource_skills, certifications, certification_skills,
session_resource_recommendations, and session_certification_recommendations.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from backend.models import (
    AnalysisSession,
    Certification,
    CertificationSkill,
    JobRole,
    LearningResource,
    ResourceSkill,
    Resume,
    SessionCertificationRecommendation,
    SessionResourceRecommendation,
    Skill,
    SkillGap,
)
from backend.services.job_matcher import UnanalyzedResumeError
from backend.services.skill_gap_analyzer import analyze_and_persist_skill_gaps

logger = logging.getLogger("careersync.services.resource_recommender")


def generate_and_persist_resource_recommendations(
    resume_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Generate and persist deterministic learning resource and certification recommendations
    targeting verified candidate skill gaps.

    Guarantees:
    - Validates resume exists and analysis_completed_at is not None.
    - Does NOT modify resume.analysis_completed_at.
    - Strictly satisfies composite foreign keys:
        (resource_id, skill_id) -> resource_skills(resource_id, skill_id)
        (certification_id, skill_id) -> certification_skills(certification_id, skill_id)
    - Idempotent: clears and refreshes recommendation records for the exact sessions being regenerated.
    - Preserves records for unrelated sessions and resumes.
    - Transactional rollback on error.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    # Ensure sessions exist for this resume
    sessions = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.resume_id == resume_id)
        .all()
    )
    if not sessions:
        analyze_and_persist_skill_gaps(resume_id=resume_id, db=db)
        sessions = (
            db.query(AnalysisSession)
            .filter(AnalysisSession.resume_id == resume_id)
            .all()
        )

    try:
        for session in sessions:
            # Atomically delete previous recommendation records ONLY for this specific session
            db.query(SessionResourceRecommendation).filter(
                SessionResourceRecommendation.session_id == session.id
            ).delete(synchronize_session=False)

            db.query(SessionCertificationRecommendation).filter(
                SessionCertificationRecommendation.session_id == session.id
            ).delete(synchronize_session=False)

            # Query skill gaps for this session
            gaps = (
                db.query(SkillGap)
                .filter(SkillGap.session_id == session.id)
                .all()
            )

            seen_res_skills: Set[Tuple[int, int]] = set()
            seen_cert_skills: Set[Tuple[int, int]] = set()

            for gap in gaps:
                # 1. Match learning resources for this gap.skill_id
                res_skills = (
                    db.query(ResourceSkill)
                    .join(LearningResource, ResourceSkill.resource_id == LearningResource.id)
                    .filter(
                        ResourceSkill.skill_id == gap.skill_id,
                        LearningResource.is_active == True,
                    )
                    .order_by(LearningResource.is_free.desc(), LearningResource.id.asc())
                    .all()
                )

                base_priority = 1 if gap.gap_priority == "CRITICAL_MISSING" else 2

                for rs in res_skills:
                    pair = (rs.resource_id, gap.skill_id)
                    if pair not in seen_res_skills:
                        seen_res_skills.add(pair)
                        priority_order = base_priority if rs.resource.is_free else (base_priority + 1)
                        rec_res = SessionResourceRecommendation(
                            session_id=session.id,
                            resource_id=rs.resource_id,
                            skill_id=gap.skill_id,
                            priority_order=priority_order,
                        )
                        db.add(rec_res)

                # 2. Match certifications for this gap.skill_id
                cert_skills = (
                    db.query(CertificationSkill)
                    .join(Certification, CertificationSkill.certification_id == Certification.id)
                    .filter(
                        CertificationSkill.skill_id == gap.skill_id,
                        Certification.is_active == True,
                    )
                    .order_by(Certification.level.asc(), Certification.id.asc())
                    .all()
                )

                for cs in cert_skills:
                    pair = (cs.certification_id, gap.skill_id)
                    if pair not in seen_cert_skills:
                        seen_cert_skills.add(pair)
                        provider_name = (
                            cs.certification.provider.name
                            if cs.certification.provider
                            else "Accredited Body"
                        )
                        gap_label = "critical required" if gap.gap_priority == "CRITICAL_MISSING" else "preferred"
                        skill_name = gap.skill.name if gap.skill else f"Skill #{gap.skill_id}"
                        cert_code = f" ({cs.certification.code})" if cs.certification.code else ""
                        rationale = (
                            f"Recommended to validate {gap_label} skill '{skill_name}' for {session.target_role_title}. "
                            f"Industry-recognized {cs.certification.level} credential{cert_code} from {provider_name}."
                        )
                        rec_cert = SessionCertificationRecommendation(
                            session_id=session.id,
                            certification_id=cs.certification_id,
                            skill_id=gap.skill_id,
                            rationale=rationale,
                        )
                        db.add(rec_cert)

        db.commit()
        logger.info("Resource and certification recommendations committed for resume %s", resume_id)

    except Exception as e:
        db.rollback()
        logger.error("Failed to generate resource recommendations for resume %s: %s", resume_id, e)
        raise e

    return get_persisted_consolidated_recommendations(resume_id=resume_id, db=db)


def get_persisted_learning_resources(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Strictly read-only retrieval of persisted learning resource recommendations.
    Does NOT trigger computations or database writes.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    query = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.resume_id == resume_id)
    )
    if target_role_id is not None:
        query = query.filter(AnalysisSession.job_role_id == target_role_id)

    sessions = query.all()
    if not sessions:
        if target_role_id is not None:
            raise ValueError(
                f"Learning resource recommendations have not been generated for resume {resume_id} and role {target_role_id}. "
                f"Please call POST /api/resumes/{resume_id}/resource-recommendations/analyze first."
            )
        raise ValueError(
            f"Learning resource recommendations have not been generated for resume {resume_id}. "
            f"Please call POST /api/resumes/{resume_id}/resource-recommendations/analyze first."
        )

    # Check whether any recommendations were generated for this resume
    total_recs_count = (
        db.query(SessionResourceRecommendation)
        .join(AnalysisSession, SessionResourceRecommendation.session_id == AnalysisSession.id)
        .filter(AnalysisSession.resume_id == resume_id)
        .count()
    )

    # If sessions exist but 0 recommendation rows across all sessions, check if recommendations analysis was run
    # (By checking if session_resource_recommendations exists or if it was analyzed)
    role_results: List[Dict[str, Any]] = []

    for session in sessions:
        rec_rows = (
            db.query(SessionResourceRecommendation)
            .filter(SessionResourceRecommendation.session_id == session.id)
            .order_by(SessionResourceRecommendation.priority_order.asc(), SessionResourceRecommendation.id.asc())
            .all()
        )

        # Get gap priority map for skills in this session
        gap_map = {
            g.skill_id: g.gap_priority for g in session.skill_gaps
        }

        items: List[Dict[str, Any]] = []
        for r in rec_rows:
            res = r.resource_skill.resource if r.resource_skill else None
            skill = r.resource_skill.skill if r.resource_skill else None
            if not res or not skill:
                continue

            items.append({
                "recommendation_id": r.id,
                "session_id": r.session_id,
                "resource_id": r.resource_id,
                "title": res.title,
                "platform_name": res.platform_name,
                "url": res.url,
                "resource_type": res.resource_type,
                "difficulty_level": res.difficulty_level,
                "is_free": res.is_free,
                "targeted_skill_id": r.skill_id,
                "targeted_skill_name": skill.name,
                "gap_priority": gap_map.get(r.skill_id, "CRITICAL_MISSING"),
                "priority_order": r.priority_order,
                "created_at": r.created_at,
            })

        role_results.append({
            "session_id": session.id,
            "job_role_id": session.job_role_id,
            "job_role_title": session.target_role_title,
            "total_resources": len(items),
            "resources": items,
        })

    # If target_role_id specified and 0 recommendations across resume, verify analysis was performed
    if total_recs_count == 0 and not any(r["total_resources"] > 0 for r in role_results):
        # Check if the candidate has zero gaps across all roles or if analysis was never run
        has_gaps = db.query(SkillGap).join(AnalysisSession).filter(AnalysisSession.resume_id == resume_id).count() > 0
        if has_gaps:
            raise ValueError(
                f"Learning resource recommendations have not been generated for resume {resume_id}. "
                f"Please call POST /api/resumes/{resume_id}/resource-recommendations/analyze first."
            )

    return {
        "resume_id": resume.id,
        "candidate_name": resume.candidate_name,
        "total_roles": len(role_results),
        "total_resources": sum(r["total_resources"] for r in role_results),
        "roles": role_results,
        "retrieved_at": datetime.now(),
    }


def get_persisted_certifications(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Strictly read-only retrieval of persisted certification recommendations.
    Does NOT trigger computations or database writes.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.analysis_completed_at is None:
        raise UnanalyzedResumeError(
            f"Resume with ID {resume_id} has not been analyzed yet. Please run resume analysis first."
        )

    query = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.resume_id == resume_id)
    )
    if target_role_id is not None:
        query = query.filter(AnalysisSession.job_role_id == target_role_id)

    sessions = query.all()
    if not sessions:
        if target_role_id is not None:
            raise ValueError(
                f"Certification recommendations have not been generated for resume {resume_id} and role {target_role_id}. "
                f"Please call POST /api/resumes/{resume_id}/resource-recommendations/analyze first."
            )
        raise ValueError(
            f"Certification recommendations have not been generated for resume {resume_id}. "
            f"Please call POST /api/resumes/{resume_id}/resource-recommendations/analyze first."
        )

    total_certs_count = (
        db.query(SessionCertificationRecommendation)
        .join(AnalysisSession, SessionCertificationRecommendation.session_id == AnalysisSession.id)
        .filter(AnalysisSession.resume_id == resume_id)
        .count()
    )

    role_results: List[Dict[str, Any]] = []

    for session in sessions:
        rec_rows = (
            db.query(SessionCertificationRecommendation)
            .filter(SessionCertificationRecommendation.session_id == session.id)
            .order_by(SessionCertificationRecommendation.id.asc())
            .all()
        )

        gap_map = {
            g.skill_id: g.gap_priority for g in session.skill_gaps
        }

        items: List[Dict[str, Any]] = []
        for c in rec_rows:
            cert = c.certification_skill.certification if c.certification_skill else None
            skill = c.certification_skill.skill if c.certification_skill else None
            if not cert or not skill:
                continue

            provider_name = cert.provider.name if cert.provider else "Accredited Body"

            items.append({
                "recommendation_id": c.id,
                "session_id": c.session_id,
                "certification_id": c.certification_id,
                "name": cert.name,
                "code": cert.code,
                "provider_name": provider_name,
                "level": cert.level,
                "official_url": cert.official_url,
                "targeted_skill_id": c.skill_id,
                "targeted_skill_name": skill.name,
                "gap_priority": gap_map.get(c.skill_id, "CRITICAL_MISSING"),
                "rationale": c.rationale,
                "created_at": c.created_at,
            })

        role_results.append({
            "session_id": session.id,
            "job_role_id": session.job_role_id,
            "job_role_title": session.target_role_title,
            "total_certifications": len(items),
            "certifications": items,
        })

    if total_certs_count == 0 and not any(r["total_certifications"] > 0 for r in role_results):
        has_gaps = db.query(SkillGap).join(AnalysisSession).filter(AnalysisSession.resume_id == resume_id).count() > 0
        if has_gaps:
            raise ValueError(
                f"Certification recommendations have not been generated for resume {resume_id}. "
                f"Please call POST /api/resumes/{resume_id}/resource-recommendations/analyze first."
            )

    return {
        "resume_id": resume.id,
        "candidate_name": resume.candidate_name,
        "total_roles": len(role_results),
        "total_certifications": sum(r["total_certifications"] for r in role_results),
        "roles": role_results,
        "retrieved_at": datetime.now(),
    }


def get_persisted_consolidated_recommendations(
    resume_id: int,
    db: Session,
    target_role_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Strictly read-only retrieval of consolidated resource and certification recommendations.
    """
    res_data = get_persisted_learning_resources(resume_id=resume_id, db=db, target_role_id=target_role_id)
    cert_data = get_persisted_certifications(resume_id=resume_id, db=db, target_role_id=target_role_id)

    res_by_role = {r["job_role_id"]: r for r in res_data["roles"]}
    cert_by_role = {c["job_role_id"]: c for c in cert_data["roles"]}

    consolidated_roles: List[Dict[str, Any]] = []
    for role_id in sorted(set(list(res_by_role.keys()) + list(cert_by_role.keys()))):
        r_info = res_by_role.get(role_id, {})
        c_info = cert_by_role.get(role_id, {})

        session_id = r_info.get("session_id") or c_info.get("session_id")
        session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first() if session_id else None
        comp_score = float(session.compatibility_score) if session and session.compatibility_score is not None else 0.00

        consolidated_roles.append({
            "session_id": session_id,
            "job_role_id": role_id,
            "job_role_title": r_info.get("job_role_title") or c_info.get("job_role_title") or f"Role #{role_id}",
            "compatibility_score": comp_score,
            "total_resources": r_info.get("total_resources", 0),
            "total_certifications": c_info.get("total_certifications", 0),
            "learning_resources": r_info.get("resources", []),
            "certifications": c_info.get("certifications", []),
        })

    return {
        "resume_id": resume_id,
        "candidate_name": res_data.get("candidate_name"),
        "total_roles_evaluated": len(consolidated_roles),
        "total_resources": res_data.get("total_resources", 0),
        "total_certifications": cert_data.get("total_certifications", 0),
        "roles": consolidated_roles,
        "generated_at": datetime.now(),
    }
