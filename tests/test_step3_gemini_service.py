"""
Unit tests for CareerSync Gemini Step 3:
- backend/services/gemini_service.py
- Mocked Gemini client interactions (ZERO real API calls)
- PII redaction verification before prompt dispatch
- Error handling: missing key, quota exhaustion (429), timeouts, invalid JSON
- Output schema compliance and zero matching score modification
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.genai import errors as genai_errors
from google.genai import types as genai_types
from google.genai import _transformers

from backend.config import settings
from backend.schemas.analysis import (
    ImprovementCategory,
    ResumeImprovementItem,
    ResumeImprovementResponse,
    SanitizedResumePayload,
    SuggestionPriority,
)
from backend.services.gemini_service import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiQuotaExceededError,
    GeminiResponseParsingError,
    GeminiServiceError,
    build_gemini_response_schema,
    build_improvement_prompt,
    generate_resume_improvement_suggestions,
    generate_resume_improvements_from_payload,
    get_gemini_client,
    strip_unsupported_schema_attributes,
)
from backend.services.privacy_sanitizer import (
    SanitizedExperienceItem,
    SanitizedProjectItem,
)


class TestGeminiService(unittest.TestCase):
    """Test suite for GeminiService with mocked Google GenAI client."""

    def setUp(self):
        """Prepare sample valid suggestions for mock responses."""
        self.sample_suggestions_data = [
            {
                "category": "PROJECTS",
                "priority": "HIGH",
                "title": "Quantify Backend Performance Impact",
                "description": "The API microservice lists Redis caching but does not report measurable benchmarks.",
                "actionable_recommendation": "State the percentage reduction in API response latency (e.g., from 250ms to 45ms).",
            },
            {
                "category": "STRUCTURE",
                "priority": "HIGH",
                "title": "Standardize Technical Section Hierarchy",
                "description": "Skills are currently scattered across work experience bullets rather than in a dedicated index.",
                "actionable_recommendation": "Group skills into structured subsections: Languages, Frameworks, Cloud, and Databases.",
            },
            {
                "category": "EXPERIENCE",
                "priority": "MEDIUM",
                "title": "Strengthen Action Verbs in Experience",
                "description": "Several responsibility bullet points begin with passive phrases like 'Responsible for' or 'Helped with'.",
                "actionable_recommendation": "Begin bullet points with strong technical verbs such as 'Architected', 'Deployed', or 'Optimized'.",
            },
            {
                "category": "KEYWORDS",
                "priority": "HIGH",
                "title": "Emphasize Core Backend Technologies",
                "description": "Target role requires Docker and FastAPI, which are mentioned only briefly in project notes.",
                "actionable_recommendation": "Explicitly highlight Docker containerization workflows in your primary backend projects.",
            },
            {
                "category": "SKILLS_FORMATTING",
                "priority": "MEDIUM",
                "title": "Categorize Database Proficiencies",
                "description": "Relational and non-relational database skills are combined into an unorganized single line.",
                "actionable_recommendation": "Distinguish between SQL (MySQL, PostgreSQL) and In-Memory/NoSQL (Redis) tools.",
            },
        ]

    def test_missing_api_key_raises_configuration_error(self):
        """Verify calling get_gemini_client without API key raises GeminiConfigurationError."""
        with patch.object(settings, "GEMINI_API_KEY", None):
            with self.assertRaises(GeminiConfigurationError) as ctx:
                get_gemini_client()
            self.assertIn("GEMINI_API_KEY is not configured", str(ctx.exception))

    def test_empty_string_api_key_raises_configuration_error(self):
        """Verify empty string or whitespace API key raises GeminiConfigurationError."""
        with patch.object(settings, "GEMINI_API_KEY", "   "):
            with self.assertRaises(GeminiConfigurationError):
                get_gemini_client()

    def test_successful_suggestion_generation(self):
        """Verify successful generation with valid mocked Gemini response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(self.sample_suggestions_data)
        mock_client.models.generate_content.return_value = mock_response

        payload = SanitizedResumePayload(
            target_role_title="Backend Developer",
            skills=["Python", "FastAPI", "MySQL", "Docker"],
            projects=[
                SanitizedProjectItem(
                    title="E-Commerce API",
                    technologies="FastAPI, MySQL, Redis",
                    description="Built order service handling high-concurrency requests.",
                )
            ],
            experience=[
                SanitizedExperienceItem(
                    role_title="Software Engineer",
                    duration="2022 - Present",
                    description="Responsible for maintaining cloud deployment pipelines.",
                )
            ],
            missing_skills=["Kubernetes", "AWS"],
        )

        result = generate_resume_improvements_from_payload(
            resume_id=42,
            payload=payload,
            session_id=10,
            target_role_id=3,
            client=mock_client,
            model="gemini-3.1-flash-lite",
        )

        self.assertIsInstance(result, ResumeImprovementResponse)
        self.assertEqual(result.resume_id, 42)
        self.assertEqual(result.session_id, 10)
        self.assertEqual(result.target_role_id, 3)
        self.assertEqual(result.target_role_title, "Backend Developer")
        self.assertEqual(result.total_suggestions, 5)
        self.assertEqual(len(result.suggestions), 5)

        # Verify individual item integrity
        first_item = result.suggestions[0]
        self.assertEqual(first_item.category, ImprovementCategory.PROJECTS)
        self.assertEqual(first_item.priority, SuggestionPriority.HIGH)
        self.assertEqual(first_item.title, "Quantify Backend Performance Impact")
        self.assertIn("Redis", first_item.description)
        self.assertIn("latency", first_item.actionable_recommendation)

        # Verify client was called with correct model and config
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-3.1-flash-lite")
        self.assertEqual(call_kwargs["config"].response_mime_type, "application/json")

    def test_pii_sanitization_before_dispatch(self):
        """Verify that candidate PII is scrubbed before prompt reaches Gemini."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(self.sample_suggestions_data)
        mock_client.models.generate_content.return_value = mock_response

        # Input containing raw personal identifiers
        raw_skills = ["Python", "FastAPI"]
        raw_projects = [
            {
                "title": "Confidential Portal",
                "technologies": "FastAPI",
                "description": "Developed by John Doe at https://github.com/johndoe/portal. Contact: john@doe.org.",
            }
        ]
        raw_experience = [
            {
                "role_title": "Backend Lead",
                "duration": "2021-2023",
                "description": "Call 555-123-4567 for references. Led team of 5 engineers.",
            }
        ]

        generate_resume_improvement_suggestions(
            resume_id=99,
            skills=raw_skills,
            projects=raw_projects,
            experience=raw_experience,
            target_role_title="Backend Developer",
            candidate_name="John Doe",
            client=mock_client,
        )

        mock_client.models.generate_content.assert_called_once()
        prompt_sent = mock_client.models.generate_content.call_args.kwargs["contents"]

        # Ensure NO personal identifiers reached the prompt
        self.assertNotIn("John Doe", prompt_sent)
        self.assertNotIn("john@doe.org", prompt_sent)
        self.assertNotIn("github.com/johndoe", prompt_sent)
        self.assertNotIn("555-123-4567", prompt_sent)

        # Verify redactor placeholders are present
        self.assertIn("[CANDIDATE]", prompt_sent)
        self.assertIn("[EMAIL REDACTED]", prompt_sent)
        self.assertIn("[LINK REDACTED]", prompt_sent)
        self.assertIn("[PHONE REDACTED]", prompt_sent)

    def test_quota_exceeded_error_handling(self):
        """Verify HTTP 429 quota exhaustion raises GeminiQuotaExceededError."""
        mock_client = MagicMock()
        api_error = genai_errors.APIError(
            429,
            {"error": {"message": "Resource has been exhausted (e.g. check quota)."}},
        )
        mock_client.models.generate_content.side_effect = api_error

        payload = SanitizedResumePayload(
            target_role_title="Data Engineer",
            skills=["Python", "SQL"],
        )

        with self.assertRaises(GeminiQuotaExceededError) as ctx:
            generate_resume_improvements_from_payload(
                resume_id=1,
                payload=payload,
                client=mock_client,
            )
        self.assertIn("rate limit or quota exceeded", str(ctx.exception))

    def test_network_timeout_error_handling(self):
        """Verify network connection timeout raises GeminiNetworkError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Connection to Gemini timed out after 30s")

        payload = SanitizedResumePayload(skills=["Python"])

        with self.assertRaises(GeminiNetworkError) as ctx:
            generate_resume_improvements_from_payload(
                resume_id=1,
                payload=payload,
                client=mock_client,
            )
        self.assertIn("Network error communicating with Gemini", str(ctx.exception))

    def test_invalid_json_response_raises_parsing_error(self):
        """Verify malformed JSON from model raises GeminiResponseParsingError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is plain text, not valid JSON {"
        mock_client.models.generate_content.return_value = mock_response

        payload = SanitizedResumePayload(skills=["Python"])

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_resume_improvements_from_payload(
                resume_id=1,
                payload=payload,
                client=mock_client,
            )
        self.assertIn("Invalid JSON returned by Gemini", str(ctx.exception))

    def test_empty_response_raises_parsing_error(self):
        """Verify empty response text raises GeminiResponseParsingError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response

        payload = SanitizedResumePayload(skills=["Python"])

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_resume_improvements_from_payload(
                resume_id=1,
                payload=payload,
                client=mock_client,
            )
        self.assertIn("empty response body", str(ctx.exception))

    def test_schema_mismatch_raises_parsing_error(self):
        """Verify JSON with invalid category or priority raises GeminiResponseParsingError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Item with invalid category 'INVALID_CATEGORY'
        bad_data = [
            {
                "category": "INVALID_CATEGORY",
                "priority": "HIGH",
                "title": "Invalid Category Item",
                "description": "Valid description length for testing schema rejection.",
                "actionable_recommendation": "Valid actionable recommendation for test.",
            }
        ]
        mock_response.text = json.dumps(bad_data)
        mock_client.models.generate_content.return_value = mock_response

        payload = SanitizedResumePayload(skills=["Python"])

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_resume_improvements_from_payload(
                resume_id=1,
                payload=payload,
                client=mock_client,
            )
        self.assertIn("failed schema validation", str(ctx.exception))

    def test_zero_suggestions_raises_parsing_error(self):
        """Verify empty list output raises GeminiResponseParsingError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_client.models.generate_content.return_value = mock_response

        payload = SanitizedResumePayload(skills=["Python"])

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_resume_improvements_from_payload(
                resume_id=1,
                payload=payload,
                client=mock_client,
            )
        self.assertIn("produced 0 valid suggestions", str(ctx.exception))

    def test_prompt_builder_contains_only_approved_fields(self):
        """Verify prompt builder formats only whitelisted fields and never personal info."""
        payload = SanitizedResumePayload(
            target_role_title="Cloud Architect",
            skills=["AWS", "Terraform", "Kubernetes"],
            projects=[
                SanitizedProjectItem(
                    title="VPC Infrastructure",
                    technologies="Terraform",
                    description="Provisioned multi-region VPC with automated failover.",
                )
            ],
            missing_skills=["GCP"],
        )
        prompt = build_improvement_prompt(payload)

        self.assertIn("Cloud Architect", prompt)
        self.assertIn("AWS, Terraform, Kubernetes", prompt)
        self.assertIn("GCP", prompt)
        self.assertIn("VPC Infrastructure", prompt)
        self.assertIn("Provisioned multi-region VPC", prompt)

        # Confirm absolute absence of raw text or contact labels
        self.assertNotIn("candidate_name", prompt)
        self.assertNotIn("candidate_email", prompt)
        self.assertNotIn("raw_text", prompt)
        self.assertNotIn("access_token", prompt)

    def test_gemini_response_schema_compatibility(self):
        """
        Regression test for Gemini 400 INVALID_ARGUMENT error:
        'Unknown name "additional_properties" at generation_config.response_schema.items'
        Ensures the generated schema does not contain additional_properties or additionalProperties.
        """
        clean_schema = build_gemini_response_schema(list[ResumeImprovementItem])
        self.assertIsInstance(clean_schema, genai_types.Schema)
        self.assertIsNone(clean_schema.items.additional_properties)

        dumped = clean_schema.model_dump(by_alias=True, exclude_none=True)
        dumped_json = json.dumps(dumped)

        # Assert no additional_properties or additionalProperties exist in the dumped payload
        self.assertNotIn("additional_properties", dumped_json)
        self.assertNotIn("additionalProperties", dumped_json)

        # Verify all required schema properties are preserved
        self.assertIn("properties", dumped["items"])
        props = dumped["items"]["properties"]
        self.assertIn("category", props)
        self.assertIn("priority", props)
        self.assertIn("title", props)
        self.assertIn("description", props)
        self.assertIn("actionable_recommendation", props)

        # Verify required fields
        required = dumped["items"]["required"]
        self.assertIn("category", required)
        self.assertIn("title", required)
        self.assertIn("description", required)
        self.assertIn("actionable_recommendation", required)

    def test_direct_t_schema_strips_additional_properties(self):
        """
        Verify that Pydantic schema json_schema_extra directly removes
        additionalProperties so default SDK transformation is also clean.
        """
        direct_schema = _transformers.t_schema(None, list[ResumeImprovementItem])
        self.assertIsNone(direct_schema.items.additional_properties)
        dumped = direct_schema.model_dump(by_alias=True, exclude_none=True)
        self.assertNotIn("additional_properties", json.dumps(dumped))
        self.assertNotIn("additionalProperties", json.dumps(dumped))


def run_all_tests():
    """Run all unit tests in this module."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestGeminiService))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
