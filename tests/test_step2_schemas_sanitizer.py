"""
Unit tests for CareerSync Gemini Step 2:
- Pydantic schema validation for ResumeImprovementItem & ResumeImprovementResponse
- PII & Privacy Sanitization for LLM payloads
- Oversized input & forbidden attribute boundary protections
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import ValidationError

from backend.schemas.analysis import (
    ImprovementCategory,
    ResumeImprovementItem,
    ResumeImprovementResponse,
    SanitizedResumePayload,
    SuggestionPriority,
)
from backend.services.privacy_sanitizer import (
    OversizedInputError,
    PrivacyViolationError,
    build_sanitized_payload,
    sanitize_dict_for_llm,
    sanitize_text,
)


class TestResumeImprovementSchemas(unittest.TestCase):
    """Test suite verifying ResumeImprovementItem & ResumeImprovementResponse schemas."""

    def test_valid_improvement_item(self):
        """Verify standard valid improvement item creates successfully."""
        item = ResumeImprovementItem(
            category=ImprovementCategory.PROJECTS,
            priority=SuggestionPriority.HIGH,
            title="Quantify Project Impact",
            description="Project descriptions currently list tasks without measurable business metrics.",
            actionable_recommendation="Add metrics such as percentage latency reduction or throughput increase.",
        )
        self.assertEqual(item.category, ImprovementCategory.PROJECTS)
        self.assertEqual(item.priority, SuggestionPriority.HIGH)
        self.assertEqual(item.title, "Quantify Project Impact")

    def test_string_enum_compatibility(self):
        """Verify plain string enum values matching DB ENUMs are accepted."""
        item = ResumeImprovementItem(
            category="STRUCTURE",
            priority="LOW",
            title="Standardize Section Order",
            description="Reorder sections so professional experience precedes educational credentials.",
            actionable_recommendation="Move Education below Experience for mid-level software roles.",
        )
        self.assertEqual(item.category, ImprovementCategory.STRUCTURE)
        self.assertEqual(item.priority, SuggestionPriority.LOW)

    def test_invalid_category_rejected(self):
        """Verify unknown category is rejected by strict validation."""
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category="FABRICATED_CATEGORY",
                priority=SuggestionPriority.HIGH,
                title="Invalid Category Test",
                description="This should fail validation due to invalid category enum value.",
                actionable_recommendation="Fix category to match allowed database enum.",
            )

    def test_invalid_priority_rejected(self):
        """Verify unknown priority is rejected by strict validation."""
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category=ImprovementCategory.KEYWORDS,
                priority="URGENT",  # Invalid priority
                title="Invalid Priority Test",
                description="This should fail validation due to invalid priority enum value.",
                actionable_recommendation="Use HIGH, MEDIUM, or LOW priority.",
            )

    def test_string_length_boundaries(self):
        """Verify min and max string length boundaries are strictly enforced."""
        # Title too short (<3 chars)
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category=ImprovementCategory.KEYWORDS,
                title="AB",
                description="Valid length description explaining the resume gap clearly.",
                actionable_recommendation="Valid length actionable recommendation.",
            )

        # Title too long (>150 chars)
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category=ImprovementCategory.KEYWORDS,
                title="A" * 151,
                description="Valid length description explaining the resume gap clearly.",
                actionable_recommendation="Valid length actionable recommendation.",
            )

        # Description too short (<10 chars)
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category=ImprovementCategory.KEYWORDS,
                title="Short Description",
                description="Too short",
                actionable_recommendation="Valid length actionable recommendation.",
            )

        # Actionable recommendation too short (<10 chars)
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category=ImprovementCategory.KEYWORDS,
                title="Short Recommendation",
                description="Valid length description explaining the resume gap clearly.",
                actionable_recommendation="Fix it",
            )

    def test_extra_fields_forbidden(self):
        """Verify extra unexpected fields are strictly forbidden by schema."""
        with self.assertRaises(ValidationError):
            ResumeImprovementItem(
                category=ImprovementCategory.STRUCTURE,
                title="No Extra Fields",
                description="Valid description explaining the observation in detail.",
                actionable_recommendation="Valid recommendation on structural alignment.",
                unexpected_field="forbidden_value",
            )

    def test_valid_improvement_response(self):
        """Verify valid response envelope structure."""
        item = ResumeImprovementItem(
            category=ImprovementCategory.SKILLS_FORMATTING,
            priority=SuggestionPriority.MEDIUM,
            title="Group Technical Proficiencies",
            description="Group tools by category (Languages, Frameworks, Cloud, Databases).",
            actionable_recommendation="Organize the skills section into clearly labeled subsections.",
        )
        response = ResumeImprovementResponse(
            resume_id=101,
            session_id=5,
            target_role_id=2,
            target_role_title="Backend Developer",
            total_suggestions=1,
            suggestions=[item],
            message="Suggestions generated successfully",
            generated_at=datetime.now(timezone.utc),
        )
        self.assertEqual(response.resume_id, 101)
        self.assertEqual(response.total_suggestions, 1)
        self.assertEqual(len(response.suggestions), 1)

    def test_response_validation_constraints(self):
        """Verify response constraints (resume_id > 0, total_suggestions >= 0)."""
        with self.assertRaises(ValidationError):
            ResumeImprovementResponse(
                resume_id=0,  # Invalid: gt=0 required
                total_suggestions=0,
                suggestions=[],
            )

        with self.assertRaises(ValidationError):
            ResumeImprovementResponse(
                resume_id=1,
                total_suggestions=-1,  # Invalid: ge=0 required
                suggestions=[],
            )


class TestPrivacySanitizer(unittest.TestCase):
    """Test suite verifying PII scrubbing, redaction, and privacy boundaries."""

    def test_email_redaction(self):
        """Verify various email formats are redacted."""
        text = "Contact me at candidate.work+tag@gmail.com or dev@sub.corp.org for inquiries."
        sanitized = sanitize_text(text)
        self.assertNotIn("candidate.work+tag@gmail.com", sanitized)
        self.assertNotIn("dev@sub.corp.org", sanitized)
        self.assertEqual(sanitized, "Contact me at [EMAIL REDACTED] or [EMAIL REDACTED] for inquiries.")

    def test_phone_redaction(self):
        """Verify various telephone number formats are redacted while years/versions are preserved."""
        text = "Call +1-800-555-0199 or 9876543210. Built with Python 3.11 in 2024 with 42 microservices."
        sanitized = sanitize_text(text)
        self.assertNotIn("800-555-0199", sanitized)
        self.assertNotIn("9876543210", sanitized)
        self.assertIn("[PHONE REDACTED]", sanitized)
        # Verify years, version numbers, and small integers are preserved
        self.assertIn("Python 3.11", sanitized)
        self.assertIn("2024", sanitized)
        self.assertIn("42 microservices", sanitized)

    def test_url_and_profile_redaction(self):
        """Verify personal links, portfolio URLs, and social profiles are redacted."""
        text = "Portfolio: https://alice-dev.io/projects. GitHub: https://github.com/alice/repo. LinkedIn: linkedin.com/in/alice-dev."
        sanitized = sanitize_text(text)
        self.assertNotIn("alice-dev.io", sanitized)
        self.assertNotIn("github.com/alice/repo", sanitized)
        self.assertNotIn("linkedin.com/in/alice-dev", sanitized)
        self.assertIn("[LINK REDACTED]", sanitized)

    def test_token_and_hash_redaction(self):
        """Verify 32-64 hex character tokens and hashes are redacted."""
        text = "Session token: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 verified."
        sanitized = sanitize_text(text)
        self.assertNotIn("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", sanitized)
        self.assertEqual(sanitized, "Session token: [TOKEN REDACTED] verified.")

    def test_candidate_name_scrubbing(self):
        """Verify candidate's name is completely redacted from project and experience text."""
        text = "John Doe led the backend migration. John developed the core caching layer."
        sanitized = sanitize_text(text, candidate_name="John Doe")
        self.assertNotIn("John Doe", sanitized)
        self.assertNotIn("John", sanitized)
        self.assertIn("[CANDIDATE] led the backend migration. [CANDIDATE] developed the core caching layer.", sanitized)

    def test_forbidden_keys_rejected(self):
        """Verify passing forbidden raw PII keys directly raises PrivacyViolationError."""
        forbidden_payloads = [
            {"candidate_email": "leaked@example.com", "skills": ["Python"]},
            {"candidate_phone": "1234567890", "skills": ["Python"]},
            {"raw_text": "Full resume text...", "skills": ["Python"]},
            {"access_token": "secret_token_123", "skills": ["Python"]},
            {"access_token_hash": "hash_value_here", "skills": ["Python"]},
            {"candidate_name": "Alice Smith", "skills": ["Python"]},
        ]
        for payload in forbidden_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(PrivacyViolationError):
                    sanitize_dict_for_llm(payload)

    def test_oversized_single_field_rejected(self):
        """Verify individual field exceeding 5000 characters is rejected immediately."""
        oversized_text = "A" * 5001
        with self.assertRaises(OversizedInputError):
            sanitize_text(oversized_text)

    def test_oversized_total_payload_rejected(self):
        """Verify total payload character count > 15000 is rejected."""
        large_projects = [
            {"title": f"Project {i}", "description": "X" * 900}
            for i in range(18)  # 18 * 900 = 16,200 chars
        ]
        with self.assertRaises(OversizedInputError):
            build_sanitized_payload(
                skills=["Python", "FastAPI"],
                projects=large_projects,
            )

    def test_end_to_end_sanitized_payload(self):
        """Verify end-to-end building of SanitizedResumePayload with zero PII."""
        skills = ["Python", "FastAPI", "MySQL", "Docker"]
        projects = [
            {
                "title": "E-Commerce Microservice",
                "technologies": "FastAPI, PostgreSQL, Redis",
                "description": "Built by Alice Smith at https://github.com/alice/ecommerce. Contact: alice@ecommerce.com.",
            }
        ]
        experience = [
            {
                "role_title": "Backend Software Engineer",
                "duration": "2022 - 2024",
                "description": "Call 555-0199 for verification. Led high-throughput API development.",
            }
        ]

        payload: SanitizedResumePayload = build_sanitized_payload(
            skills=skills,
            projects=projects,
            experience=experience,
            target_role_title="Senior Backend Developer",
            missing_skills=["Kubernetes", "AWS"],
            candidate_name="Alice Smith",
        )

        self.assertIsInstance(payload, SanitizedResumePayload)
        self.assertEqual(payload.target_role_title, "Senior Backend Developer")
        self.assertEqual(payload.skills, ["Python", "FastAPI", "MySQL", "Docker"])
        self.assertEqual(payload.missing_skills, ["Kubernetes", "AWS"])

        # Check project was properly scrubbed
        project_desc = payload.projects[0].description
        self.assertNotIn("Alice Smith", project_desc)
        self.assertNotIn("alice@ecommerce.com", project_desc)
        self.assertNotIn("github.com/alice/ecommerce", project_desc)
        self.assertIn("[CANDIDATE]", project_desc)
        self.assertIn("[EMAIL REDACTED]", project_desc)
        self.assertIn("[LINK REDACTED]", project_desc)

        # Check experience was properly scrubbed
        exp_desc = payload.experience[0].description
        self.assertNotIn("555-0199", exp_desc)
        self.assertIn("[PHONE REDACTED]", exp_desc)

        # Confirm strict serialization contains NO forbidden fields
        dumped = payload.model_dump()
        for forbidden in ("raw_text", "candidate_name", "candidate_email", "candidate_phone", "access_token"):
            self.assertNotIn(forbidden, dumped)


def run_all_tests():
    """Run all unit tests in this module."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestResumeImprovementSchemas))
    suite.addTests(loader.loadTestsFromTestCase(TestPrivacySanitizer))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
