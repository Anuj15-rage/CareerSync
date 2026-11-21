"""
Step 3: Unit and API integration tests for Gemini-powered Learning Roadmap Endpoint
- POST /api/resumes/{resume_id}/resource-recommendations/roadmap
- Authentication & access token binding (X-Resume-Token via verify_resume_access)
- Target role and session scoping (prevents cross-role resource mixing)
- Error mapping (400, 404, 500, 502, 503)
- Verification that existing resource recommendation endpoints continue to function
- Fully isolated in-memory SQLite database
"""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    AnalysisSession,
    Certification,
    CertificationSkill,
    JobRole,
    LearningResource,
    ResourceSkill,
    Resume,
    ResumeSkill,
    SessionCertificationRecommendation,
    SessionResourceRecommendation,
    Skill,
    SkillGap,
)
from backend.schemas.recommendation import (
    EnrichedLearningRoadmapResponse,
    EnrichedRoadmapItem,
    EnrichedRoadmapPhase,
    RoadmapItemType,
)
from backend.services.gemini_service import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiQuotaExceededError,
    GeminiResponseParsingError,
    GeminiServiceError,
)
from backend.services.security import (
    generate_access_token,
    hash_access_token,
    store_resume_token_hash,
)
from tests.test_sqlite_fixtures import setup_sqlite_test_env


class TestLearningRoadmapAPI(unittest.TestCase):
    """Test suite for POST /api/resumes/{resume_id}/resource-recommendations/roadmap."""

    @classmethod
    def setUpClass(cls):
        """Initialize isolated SQLite test database and seed catalog."""
        cls.engine, cls.SessionLocal = setup_sqlite_test_env(app)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Clean up dependency overrides."""
        app.dependency_overrides.clear()

    def setUp(self):
        """Seed a clean test resume, session, gaps, and recommendations."""
        self.db = self.SessionLocal()

        self.raw_token = generate_access_token()
        self.token_hash = hash_access_token(self.raw_token)

        # 1. Create analyzed test resume
        self.resume = Resume(
            file_name="candidate.pdf",
            file_type="PDF",
            file_size_bytes=2048,
            file_hash="hash_" + self.raw_token[:12],
            raw_text="Sample candidate resume with Python and SQL",
            parsing_status="PARSED",
            candidate_name="Bob Engineer",
            candidate_email="bob@example.com",
            candidate_phone="+1-555-0144",
            analysis_completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)
        self.resume_id = self.resume.id

        store_resume_token_hash(self.resume_id, self.token_hash, self.db)

        # 2. Add verified resume skill
        python_skill = self.db.query(Skill).filter(Skill.normalized_name == "python").first()
        if not python_skill:
            python_skill = Skill(name="Python", normalized_name="python", category="PROGRAMMING_LANGUAGE")
            self.db.add(python_skill)
            self.db.commit()
            self.db.refresh(python_skill)

        self.resume_skill = ResumeSkill(
            resume_id=self.resume_id,
            skill_id=python_skill.id,
            extraction_source="SKILLS_SECTION",
        )
        self.db.add(self.resume_skill)

        # 3. Get or create test job role
        self.role = self.db.query(JobRole).first()
        self.role_id = self.role.id

        # 4. Create analysis session for this role
        self.session = AnalysisSession(
            resume_id=self.resume_id,
            job_role_id=self.role_id,
            target_role_title=self.role.title,
            target_job_description="Sample job description",
            compatibility_score=75.0,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(self.session)
        self.db.commit()
        self.db.refresh(self.session)
        self.session_id = self.session.id

        # 5. Add a skill gap for this session
        docker_skill = self.db.query(Skill).filter(Skill.normalized_name == "docker").first()
        if not docker_skill:
            docker_skill = Skill(name="Docker", normalized_name="docker", category="TOOL_PLATFORM")
            self.db.add(docker_skill)
            self.db.commit()
            self.db.refresh(docker_skill)
        self.docker_skill_id = docker_skill.id

        self.skill_gap = SkillGap(
            session_id=self.session_id,
            skill_id=docker_skill.id,
            gap_priority="CRITICAL_MISSING",
            reason="Missing required skill",
        )
        self.db.add(self.skill_gap)
        self.db.commit()

        # 6. Add a resource recommendation for this session
        res_skill = self.db.query(ResourceSkill).filter(ResourceSkill.skill_id == docker_skill.id).first()
        if not res_skill:
            resource = LearningResource(
                title="Official Docker Guide",
                platform_name="Docker Docs",
                url="https://docs.docker.com/test",
                resource_type="DOCUMENTATION",
                difficulty_level="BEGINNER",
                is_free=True,
            )
            self.db.add(resource)
            self.db.commit()
            self.db.refresh(resource)
            res_skill = ResourceSkill(resource_id=resource.id, skill_id=docker_skill.id)
            self.db.add(res_skill)
            self.db.commit()
            self.db.refresh(res_skill)

        self.res_rec = SessionResourceRecommendation(
            session_id=self.session_id,
            resource_id=res_skill.resource_id,
            skill_id=docker_skill.id,
            priority_order=1,
        )
        self.db.add(self.res_rec)

        # 7. Add a certification recommendation for this session
        cert_skill = self.db.query(CertificationSkill).first()
        if cert_skill:
            self.cert_rec = SessionCertificationRecommendation(
                session_id=self.session_id,
                certification_id=cert_skill.certification_id,
                skill_id=cert_skill.skill_id,
                rationale="Industry standard certification.",
            )
            self.db.add(self.cert_rec)

        self.db.commit()

        # Auth headers
        self.auth_headers = {"X-Resume-Token": self.raw_token}

    def tearDown(self):
        """Clean up session."""
        self.db.close()

    @patch("backend.api.resumes.generate_learning_roadmap")
    def test_successful_roadmap_generation_endpoint(self, mock_gen_roadmap):
        """POST /resource-recommendations/roadmap returns HTTP 200 and enriched roadmap response."""
        mock_item = EnrichedRoadmapItem(
            item_type=RoadmapItemType.LEARNING_RESOURCE,
            resource_id=self.res_rec.resource_id,
            targeted_skill_name="Docker",
            personalized_explanation="Hands-on guide to container workflows.",
            sequence_order=1,
            title="Official Docker Guide",
            platform_or_provider="Docker Docs",
            url="https://docs.docker.com/test",
            difficulty_or_level="BEGINNER",
            is_free=True,
        )
        mock_phase = EnrichedRoadmapPhase(
            phase_number=1,
            title="Phase 1: Containers",
            description="Foundational DevOps skills.",
            items=[mock_item],
        )
        mock_response = EnrichedLearningRoadmapResponse(
            resume_id=self.resume_id,
            target_role_id=self.role_id,
            target_role_title=self.role.title,
            total_phases=1,
            total_items=1,
            phases=[mock_phase],
            summary="Personalized roadmap for backend role.",
            generated_at=datetime.now(timezone.utc),
        )
        mock_gen_roadmap.return_value = mock_response

        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["resume_id"], self.resume_id)
        self.assertEqual(data["target_role_title"], self.role.title)
        self.assertEqual(data["total_phases"], 1)
        self.assertEqual(len(data["phases"]), 1)
        self.assertEqual(data["phases"][0]["items"][0]["title"], "Official Docker Guide")
        self.assertEqual(data["phases"][0]["items"][0]["url"], "https://docs.docker.com/test")

        # Verify arguments passed to service
        mock_gen_roadmap.assert_called_once()
        kwargs = mock_gen_roadmap.call_args.kwargs
        self.assertEqual(kwargs["resume_id"], self.resume_id)
        self.assertEqual(kwargs["target_role_id"], self.role_id)
        self.assertIn("Docker", kwargs["missing_skills"])

    def test_missing_access_token_returns_404(self):
        """Missing X-Resume-Token returns uniform 404 Not Found."""
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}"
        )
        self.assertEqual(res.status_code, 404)

    def test_invalid_access_token_returns_404(self):
        """Invalid X-Resume-Token returns uniform 404 Not Found."""
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers={"X-Resume-Token": "invalid_wrong_token"},
        )
        self.assertEqual(res.status_code, 404)

    def test_cross_resume_token_access_returns_404(self):
        """Token belonging to resume A cannot access resume B's roadmap."""
        other_token = generate_access_token()
        other_hash = hash_access_token(other_token)
        other_resume = Resume(
            file_name="other.pdf",
            file_type="PDF",
            file_size_bytes=1024,
            file_hash="hash_other_123",
            raw_text="Other resume text",
            parsing_status="PARSED",
            analysis_completed_at=datetime.now(timezone.utc),
        )
        self.db.add(other_resume)
        self.db.commit()
        self.db.refresh(other_resume)
        store_resume_token_hash(other_resume.id, other_hash, self.db)

        # Attempt to access resume 1 with resume 2's token
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers={"X-Resume-Token": other_token},
        )
        self.assertEqual(res.status_code, 404)

    def test_unanalyzed_resume_returns_400(self):
        """Resume with analysis_completed_at = None returns HTTP 400."""
        self.resume.analysis_completed_at = None
        self.db.commit()

        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("has not been analyzed yet", res.json()["detail"])

    def test_nonexistent_target_role_returns_404(self):
        """Target role ID that does not exist returns HTTP 404."""
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id=99999",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("JobRole with ID 99999 not found", res.json()["detail"])

    def test_target_role_without_analysis_session_returns_404(self):
        """Target role with no analysis session for this resume returns HTTP 404."""
        # Find another role that does not have an analysis session
        other_role = self.db.query(JobRole).filter(JobRole.id != self.role_id).first()
        if other_role:
            res = self.client.post(
                f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={other_role.id}",
                headers=self.auth_headers,
            )
            self.assertEqual(res.status_code, 404)
            self.assertIn("No analysis session found", res.json()["detail"])

    @patch("backend.api.resumes.generate_learning_roadmap")
    def test_session_isolation_prevents_resource_leakage(self, mock_gen_roadmap):
        """Verify only resources belonging to the requested session are passed to generate_learning_roadmap."""
        # Create a second session for another role with its own distinct resource
        other_role = self.db.query(JobRole).filter(JobRole.id != self.role_id).first()
        if other_role:
            session2 = AnalysisSession(
                resume_id=self.resume_id,
                job_role_id=other_role.id,
                target_role_title=other_role.title,
                target_job_description="Description 2",
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(session2)
            self.db.commit()
            self.db.refresh(session2)

            mock_gen_roadmap.return_value = EnrichedLearningRoadmapResponse(
                resume_id=self.resume_id,
                target_role_id=self.role_id,
                target_role_title=self.role.title,
                total_phases=0,
                total_items=0,
                phases=[],
                generated_at=datetime.now(timezone.utc),
            )

            self.client.post(
                f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
                headers=self.auth_headers,
            )

            # Assert only session 1 resources were retrieved and passed
            called_resources = mock_gen_roadmap.call_args.kwargs["learning_resources"]
            for r in called_resources:
                self.assertEqual(r["resource_id"], self.res_rec.resource_id)

    @patch("backend.api.resumes.generate_learning_roadmap")
    def test_gemini_configuration_error_maps_to_500(self, mock_gen_roadmap):
        """GeminiConfigurationError maps to HTTP 500 with descriptive detail."""
        mock_gen_roadmap.side_effect = GeminiConfigurationError("Missing API key")
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 500)
        self.assertIn("GEMINI_API_KEY is not configured", res.json()["detail"])

    @patch("backend.api.resumes.generate_learning_roadmap")
    def test_gemini_quota_error_maps_to_503(self, mock_gen_roadmap):
        """GeminiQuotaExceededError maps to HTTP 503."""
        mock_gen_roadmap.side_effect = GeminiQuotaExceededError("Rate limit exceeded")
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("quota exceeded", res.json()["detail"].lower())

    @patch("backend.api.resumes.generate_learning_roadmap")
    def test_gemini_network_error_maps_to_503(self, mock_gen_roadmap):
        """GeminiNetworkError maps to HTTP 503."""
        mock_gen_roadmap.side_effect = GeminiNetworkError("Connection timed out")
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("network error", res.json()["detail"].lower())

    @patch("backend.api.resumes.generate_learning_roadmap")
    def test_gemini_parsing_error_maps_to_502(self, mock_gen_roadmap):
        """GeminiResponseParsingError maps to HTTP 502 Bad Gateway."""
        mock_gen_roadmap.side_effect = GeminiResponseParsingError("Unapproved resource ID 999")
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 502)
        self.assertIn("Invalid or malformed structured response", res.json()["detail"])

    @patch("backend.api.resumes.generate_and_persist_resource_recommendations")
    def test_database_failure_during_base_recommendation_generation_returns_500(self, mock_base_gen):
        """Database failure while generating base recommendations returns HTTP 500."""
        # Delete existing recommendations to trigger auto-generation branch
        self.db.query(SessionResourceRecommendation).filter(SessionResourceRecommendation.session_id == self.session_id).delete()
        self.db.query(SessionCertificationRecommendation).filter(SessionCertificationRecommendation.session_id == self.session_id).delete()
        self.db.commit()

        mock_base_gen.side_effect = RuntimeError("Database connection crashed")
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/resource-recommendations/roadmap?target_role_id={self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 500)
        self.assertIn("Database error generating base recommendations", res.json()["detail"])

    def test_existing_resource_recommendation_endpoints_still_work(self):
        """Verify existing GET /resource-recommendations endpoints continue to function."""
        # 1. Consolidated
        res1 = self.client.get(
            f"/api/resumes/{self.resume_id}/resource-recommendations",
            headers=self.auth_headers,
        )
        self.assertEqual(res1.status_code, 200)

        # 2. Single role consolidated
        res2 = self.client.get(
            f"/api/resumes/{self.resume_id}/resource-recommendations/{self.role_id}",
            headers=self.auth_headers,
        )
        self.assertEqual(res2.status_code, 200)

        # 3. Learning resources
        res3 = self.client.get(
            f"/api/resumes/{self.resume_id}/learning-resources",
            headers=self.auth_headers,
        )
        self.assertEqual(res3.status_code, 200)

        # 4. Certifications
        res4 = self.client.get(
            f"/api/resumes/{self.resume_id}/certifications",
            headers=self.auth_headers,
        )
        self.assertEqual(res4.status_code, 200)


if __name__ == "__main__":
    unittest.main()
