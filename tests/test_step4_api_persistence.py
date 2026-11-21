"""
Unit tests for CareerSync Gemini Step 4:
- API endpoint authentication and token binding (verify_resume_access)
- Safe database persistence into resume_improvement_suggestions
- Transactional rollback on failure
- Error status mappings (500, 502, 503) for Gemini service failures
- Read-only retrieval via GET endpoint
- Fully isolated in-memory SQLite execution (zero MySQL access)
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
    JobRole,
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeImprovementSuggestion,
    ResumeProject,
    ResumeSkill,
    Skill,
)
from backend.schemas.analysis import (
    ImprovementCategory,
    ResumeImprovementItem,
    ResumeImprovementResponse,
    SuggestionPriority,
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


class TestGeminiAPIPersistence(unittest.TestCase):
    """Test suite for Step 4 Gemini API endpoints and database persistence."""

    @classmethod
    def setUpClass(cls):
        """Initialize isolated SQLite test database and seed master catalog."""
        cls.engine, cls.SessionLocal = setup_sqlite_test_env(app)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Clean up dependency overrides."""
        app.dependency_overrides.clear()

    def setUp(self):
        """Create a fresh test session and helper data for each test."""
        self.db = self.SessionLocal()

        # Generate access token
        self.raw_token = generate_access_token()
        self.token_hash = hash_access_token(self.raw_token)

        # Create analyzed resume
        self.resume = Resume(
            file_name="candidate_profile.pdf",
            file_type="PDF",
            file_size_bytes=1024,
            file_hash="hash_" + self.raw_token[:10],
            raw_text="Sample raw resume content",
            parsing_status="PARSED",
            candidate_name="Alice Candidate",
            candidate_email="alice@example.com",
            candidate_phone="+1-555-0199",
            analysis_completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)
        self.resume_id = self.resume.id

        # Register access token hash
        store_resume_token_hash(self.resume_id, self.token_hash, self.db)

        # Attach sample verified skills
        python_skill = self.db.query(Skill).filter(Skill.name == "Python").first()
        fastapi_skill = self.db.query(Skill).filter(Skill.name == "FastAPI").first()
        if python_skill:
            self.db.add(ResumeSkill(resume_id=self.resume_id, skill_id=python_skill.id, extraction_source="SKILLS_SECTION"))
        if fastapi_skill:
            self.db.add(ResumeSkill(resume_id=self.resume_id, skill_id=fastapi_skill.id, extraction_source="SKILLS_SECTION"))

        # Attach sample project & experience
        self.db.add(
            ResumeProject(
                resume_id=self.resume_id,
                title="Microservice Platform",
                technologies_used="FastAPI, Redis",
                description="Built high-throughput payment processing APIs.",
            )
        )
        self.db.add(
            ResumeExperience(
                resume_id=self.resume_id,
                organization="Tech Corp",
                role_title="Backend Developer",
                duration="2022 - Present",
                description="Designed database schemas and API endpoints.",
            )
        )
        self.db.commit()

        # Mocked sample suggestions from Gemini service
        self.mock_suggestions = [
            ResumeImprovementItem(
                category=ImprovementCategory.PROJECTS,
                priority=SuggestionPriority.HIGH,
                title="Quantify API Performance",
                description="Payment processing lists high throughput but omits request-per-second benchmarks.",
                actionable_recommendation="State peak requests per second and p99 latency benchmarks achieved.",
            ),
            ResumeImprovementItem(
                category=ImprovementCategory.STRUCTURE,
                priority=SuggestionPriority.MEDIUM,
                title="Consolidate Backend Proficiencies",
                description="Tools and languages should be grouped cleanly into labeled sections.",
                actionable_recommendation="Organize technical skills into Languages, Frameworks, and Databases.",
            ),
            ResumeImprovementItem(
                category=ImprovementCategory.KEYWORDS,
                priority=SuggestionPriority.HIGH,
                title="Emphasize Containerization Experience",
                description="Target role expects Docker knowledge which is not prominently featured.",
                actionable_recommendation="Highlight container deployment workflows used in your microservices.",
            ),
        ]

        self.mock_response = ResumeImprovementResponse(
            resume_id=self.resume_id,
            target_role_title="Backend Developer",
            total_suggestions=3,
            suggestions=self.mock_suggestions,
            message="Resume improvement suggestions generated successfully.",
            generated_at=datetime.now(timezone.utc),
        )

    def tearDown(self):
        """Clean up database session."""
        self.db.close()

    def test_unauthenticated_generate_and_get_rejected(self):
        """Verify requests without X-Resume-Token return uniform 404 Not Found."""
        gen_res = self.client.post(f"/api/resumes/{self.resume_id}/improvement-suggestions/generate")
        self.assertEqual(gen_res.status_code, 404)

        get_res = self.client.get(f"/api/resumes/{self.resume_id}/improvement-suggestions")
        self.assertEqual(get_res.status_code, 404)

    def test_wrong_token_rejected(self):
        """Verify request with invalid/mismatched token returns uniform 404 Not Found."""
        bad_headers = {"X-Resume-Token": "invalid_wrong_token_xyz"}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=bad_headers,
        )
        self.assertEqual(res.status_code, 404)

    def test_unanalyzed_resume_rejected(self):
        """Verify unanalyzed resume returns 400 Bad Request."""
        # Create unanalyzed resume
        unanalyzed_token = generate_access_token()
        unanalyzed_resume = Resume(
            file_name="unanalyzed.pdf",
            file_type="PDF",
            file_size_bytes=512,
            file_hash="hash_unanalyzed",
            raw_text="Unanalyzed raw text",
            parsing_status="PARSED",
            analysis_completed_at=None,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(unanalyzed_resume)
        self.db.commit()
        store_resume_token_hash(unanalyzed_resume.id, hash_access_token(unanalyzed_token), self.db)

        headers = {"X-Resume-Token": unanalyzed_token}
        res = self.client.post(
            f"/api/resumes/{unanalyzed_resume.id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("has not been analyzed yet", res.json()["detail"])

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_successful_generation_and_persistence(self, mock_gemini):
        """Verify successful generation persists items to database transactionally."""
        mock_gemini.return_value = self.mock_response

        headers = {"X-Resume-Token": self.raw_token}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["resume_id"], self.resume_id)
        self.assertEqual(data["total_suggestions"], 3)
        self.assertEqual(len(data["suggestions"]), 3)

        # Verify database persistence directly
        persisted = (
            self.db.query(ResumeImprovementSuggestion)
            .join(AnalysisSession, AnalysisSession.id == ResumeImprovementSuggestion.session_id)
            .filter(AnalysisSession.resume_id == self.resume_id)
            .all()
        )
        self.assertEqual(len(persisted), 3)

        # Check category and priority ENUM validity
        categories = [p.category for p in persisted]
        self.assertIn("PROJECTS", categories)
        self.assertIn("STRUCTURE", categories)
        self.assertIn("KEYWORDS", categories)

        for p in persisted:
            # Check JSON payload inside suggestion column
            payload = json.loads(p.suggestion)
            self.assertIn("title", payload)
            self.assertIn("description", payload)
            self.assertIn("actionable_recommendation", payload)

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_get_persisted_suggestions(self, mock_gemini):
        """Verify GET endpoint retrieves previously persisted suggestions without LLM calls."""
        mock_gemini.return_value = self.mock_response

        headers = {"X-Resume-Token": self.raw_token}
        # Step 1: Generate & persist
        post_res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(post_res.status_code, 200)

        # Step 2: Read back via GET
        get_res = self.client.get(
            f"/api/resumes/{self.resume_id}/improvement-suggestions",
            headers=headers,
        )
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["resume_id"], self.resume_id)
        self.assertEqual(data["total_suggestions"], 3)
        self.assertEqual(len(data["suggestions"]), 3)

        # Verify suggestion details
        titles = [s["title"] for s in data["suggestions"]]
        self.assertIn("Quantify API Performance", titles)
        self.assertIn("Consolidate Backend Proficiencies", titles)
        self.assertIn("Emphasize Containerization Experience", titles)

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_missing_api_key_returns_500(self, mock_gemini):
        """Verify unconfigured Gemini API key returns 500 Internal Server Error."""
        mock_gemini.side_effect = GeminiConfigurationError("Missing GEMINI_API_KEY")

        headers = {"X-Resume-Token": self.raw_token}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res.status_code, 500)
        self.assertIn("Gemini API is not configured", res.json()["detail"])

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_quota_exceeded_returns_503(self, mock_gemini):
        """Verify Gemini 429 quota exhaustion returns 503 Service Unavailable."""
        mock_gemini.side_effect = GeminiQuotaExceededError("Rate limit exceeded")

        headers = {"X-Resume-Token": self.raw_token}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("rate limit or quota exceeded", res.json()["detail"])

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_network_error_returns_503(self, mock_gemini):
        """Verify network connection timeout returns 503 Service Unavailable."""
        mock_gemini.side_effect = GeminiNetworkError("Connection timed out")

        headers = {"X-Resume-Token": self.raw_token}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Network error communicating", res.json()["detail"])

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_invalid_gemini_response_returns_502(self, mock_gemini):
        """Verify malformed Gemini JSON output returns 502 Bad Gateway."""
        mock_gemini.side_effect = GeminiResponseParsingError("Invalid JSON structure")

        headers = {"X-Resume-Token": self.raw_token}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res.status_code, 502)
        self.assertIn("Invalid or malformed structured response", res.json()["detail"])

    def test_target_role_not_found_returns_404(self):
        """Verify non-existent target_role_id returns 404 Not Found."""
        headers = {"X-Resume-Token": self.raw_token}
        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate?target_role_id=99999",
            headers=headers,
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Active JobRole with ID 99999 not found", res.json()["detail"])

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_idempotent_regeneration_replaces_old_suggestions(self, mock_gemini):
        """Verify regenerating suggestions replaces previous session records cleanly."""
        mock_gemini.return_value = self.mock_response
        headers = {"X-Resume-Token": self.raw_token}

        # First run: 3 suggestions
        res1 = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res1.status_code, 200)

        # Second run with different suggestions count: 1 suggestion
        single_suggestion_response = ResumeImprovementResponse(
            resume_id=self.resume_id,
            target_role_title="Backend Developer",
            total_suggestions=1,
            suggestions=[self.mock_suggestions[0]],
            message="Regenerated suggestions successfully.",
            generated_at=datetime.now(timezone.utc),
        )
        mock_gemini.return_value = single_suggestion_response

        res2 = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res2.status_code, 200)

        # Verify database has only the replaced 1 suggestion (not 3 + 1 = 4)
        persisted = (
            self.db.query(ResumeImprovementSuggestion)
            .join(AnalysisSession, AnalysisSession.id == ResumeImprovementSuggestion.session_id)
            .filter(AnalysisSession.resume_id == self.resume_id)
            .all()
        )
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].category, "PROJECTS")

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_general_session_created_with_null_job_role_id(self, mock_gemini):
        """Verify omitting target_role_id creates a dedicated general session with job_role_id = NULL."""
        mock_gemini.return_value = self.mock_response
        headers = {"X-Resume-Token": self.raw_token}

        res = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)

        # Query session directly
        session = (
            self.db.query(AnalysisSession)
            .filter(AnalysisSession.resume_id == self.resume_id)
            .first()
        )
        self.assertIsNotNone(session)
        self.assertIsNone(session.job_role_id)
        self.assertEqual(session.target_role_title, "General Software Engineering Profile")

    @patch("backend.api.resumes.generate_resume_improvement_suggestions")
    def test_general_and_role_suggestions_isolation(self, mock_gemini):
        """Verify general and role-specific suggestions are strictly isolated on generation and replacement."""
        headers = {"X-Resume-Token": self.raw_token}

        # 1. Generate 3 General suggestions (target_role_id=None)
        mock_gemini.return_value = ResumeImprovementResponse(
            resume_id=self.resume_id,
            target_role_title="General Software Engineering Profile",
            total_suggestions=3,
            suggestions=self.mock_suggestions,
            message="General suggestions generated.",
            generated_at=datetime.now(timezone.utc),
        )
        res_gen = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res_gen.status_code, 200)

        # 2. Generate 2 Role-Specific suggestions (target_role_id=1)
        role_suggestions = self.mock_suggestions[:2]
        mock_gemini.return_value = ResumeImprovementResponse(
            resume_id=self.resume_id,
            target_role_id=1,
            target_role_title="Python Backend Developer",
            total_suggestions=2,
            suggestions=role_suggestions,
            message="Role suggestions generated.",
            generated_at=datetime.now(timezone.utc),
        )
        res_role = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate?target_role_id=1",
            headers=headers,
        )
        self.assertEqual(res_role.status_code, 200)

        # Verify database has both: 3 general suggestions and 2 role suggestions (total 5)
        gen_session = (
            self.db.query(AnalysisSession)
            .filter(AnalysisSession.resume_id == self.resume_id, AnalysisSession.job_role_id.is_(None))
            .first()
        )
        role_session = (
            self.db.query(AnalysisSession)
            .filter(AnalysisSession.resume_id == self.resume_id, AnalysisSession.job_role_id == 1)
            .first()
        )
        self.assertIsNotNone(gen_session)
        self.assertIsNotNone(role_session)

        gen_count = self.db.query(ResumeImprovementSuggestion).filter(ResumeImprovementSuggestion.session_id == gen_session.id).count()
        role_count = self.db.query(ResumeImprovementSuggestion).filter(ResumeImprovementSuggestion.session_id == role_session.id).count()
        self.assertEqual(gen_count, 3)
        self.assertEqual(role_count, 2)

        # 3. Regenerate General suggestions with 1 item: must NOT delete Role suggestions!
        mock_gemini.return_value = ResumeImprovementResponse(
            resume_id=self.resume_id,
            target_role_title="General Software Engineering Profile",
            total_suggestions=1,
            suggestions=[self.mock_suggestions[0]],
            message="Regenerated general.",
            generated_at=datetime.now(timezone.utc),
        )
        res_gen2 = self.client.post(
            f"/api/resumes/{self.resume_id}/improvement-suggestions/generate",
            headers=headers,
        )
        self.assertEqual(res_gen2.status_code, 200)

        gen_count_after = self.db.query(ResumeImprovementSuggestion).filter(ResumeImprovementSuggestion.session_id == gen_session.id).count()
        role_count_after = self.db.query(ResumeImprovementSuggestion).filter(ResumeImprovementSuggestion.session_id == role_session.id).count()
        self.assertEqual(gen_count_after, 1, "General suggestions should be replaced with 1")
        self.assertEqual(role_count_after, 2, "Role suggestions must remain intact at 2")

        # 4. Test GET isolation:
        # GET without params -> returns general suggestions (count = 1)
        get_gen = self.client.get(f"/api/resumes/{self.resume_id}/improvement-suggestions", headers=headers)
        self.assertEqual(get_gen.status_code, 200)
        self.assertEqual(get_gen.json()["total_suggestions"], 1)
        self.assertEqual(get_gen.json()["target_role_title"], "General Software Engineering Profile")

        # GET with ?target_role_id=1 -> returns role suggestions (count = 2)
        get_role = self.client.get(f"/api/resumes/{self.resume_id}/improvement-suggestions?target_role_id=1", headers=headers)
        self.assertEqual(get_role.status_code, 200)
        self.assertEqual(get_role.json()["total_suggestions"], 2)
        self.assertEqual(get_role.json()["target_role_id"], 1)

        # GET with ?target_role_id=2 (un-generated role) -> returns 0 suggestions
        get_role2 = self.client.get(f"/api/resumes/{self.resume_id}/improvement-suggestions?target_role_id=2", headers=headers)
        self.assertEqual(get_role2.status_code, 200)
        self.assertEqual(get_role2.json()["total_suggestions"], 0)


def run_all_tests():
    """Run all unit tests in this module."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestGeminiAPIPersistence))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
