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
from backend.schemas.recommendation import (
    EnrichedLearningRoadmapResponse,
    EnrichedRoadmapItem,
    EnrichedRoadmapPhase,
    GeminiRoadmapItem,
    GeminiRoadmapOutput,
    GeminiRoadmapPhase,
    PersonalizedRoadmapResponse,
    RoadmapItem,
    RoadmapItemType,
    RoadmapPhase,
)
from backend.services.gemini_service import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiQuotaExceededError,
    GeminiResponseParsingError,
    GeminiServiceError,
    build_gemini_response_schema,
    build_improvement_prompt,
    build_roadmap_prompt,
    generate_learning_roadmap,
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
    suite.addTests(loader.loadTestsFromTestCase(TestGeminiRoadmapService))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


class TestGeminiRoadmapService(unittest.TestCase):
    """Test suite for learning roadmap generation in GeminiService."""

    def setUp(self):
        self.sample_resources = [
            {
                "resource_id": 10,
                "title": "Official Docker Tutorial",
                "platform_name": "Docker Docs",
                "url": "https://docs.docker.com/get-started/",
                "targeted_skill_name": "Docker",
                "difficulty_level": "BEGINNER",
                "is_free": True,
            },
            {
                "resource_id": 12,
                "title": "FastAPI Async Web Development",
                "platform_name": "FastAPI Docs",
                "url": "https://fastapi.tiangolo.com/tutorial/",
                "targeted_skill_name": "FastAPI",
                "difficulty_level": "INTERMEDIATE",
                "is_free": True,
            },
        ]
        self.sample_certifications = [
            {
                "certification_id": 3,
                "name": "AWS Certified Cloud Practitioner",
                "code": "CLF-C02",
                "provider_name": "Amazon Web Services",
                "official_url": "https://aws.amazon.com/certification/certified-cloud-practitioner/",
                "level": "ENTRY",
                "targeted_skill_name": "AWS",
            }
        ]
        self.valid_gemini_roadmap_payload = {
            "target_role_title": "Backend Software Engineer",
            "total_phases": 2,
            "total_items": 3,
            "summary": "Targeted phased curriculum bridging Docker, FastAPI, and AWS infrastructure gaps.",
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Phase 1: Backend Architecture & Containers",
                    "description": "Master asynchronous REST endpoints and containerized deployments.",
                    "items": [
                        {
                            "item_type": "LEARNING_RESOURCE",
                            "resource_id": 12,
                            "targeted_skill_name": "FastAPI",
                            "personalized_explanation": "Build on your existing Python background by mastering asynchronous API development with FastAPI.",
                            "sequence_order": 1,
                        },
                        {
                            "item_type": "LEARNING_RESOURCE",
                            "resource_id": 10,
                            "targeted_skill_name": "Docker",
                            "personalized_explanation": "Containerize your FastAPI applications to bridge deployment and DevOps requirements for backend roles.",
                            "sequence_order": 2,
                        },
                    ],
                },
                {
                    "phase_number": 2,
                    "title": "Phase 2: Cloud Infrastructure & Validation",
                    "description": "Demonstrate foundational cloud proficiency with an accredited credential.",
                    "items": [
                        {
                            "item_type": "CERTIFICATION",
                            "certification_id": 3,
                            "targeted_skill_name": "AWS",
                            "personalized_explanation": "Validate your cloud architecture knowledge to demonstrate readiness for production cloud deployments.",
                            "sequence_order": 1,
                        }
                    ],
                },
            ],
        }

    def test_successful_roadmap_generation(self):
        """Verify successful roadmap generation and database enrichment from valid mocked Gemini response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(self.valid_gemini_roadmap_payload)
        mock_client.models.generate_content.return_value = mock_response

        roadmap = generate_learning_roadmap(
            resume_id=1,
            target_role_title="Backend Software Engineer",
            target_role_id=5,
            verified_skills=["Python", "SQL", "Git"],
            missing_skills=["Docker", "FastAPI", "AWS"],
            learning_resources=self.sample_resources,
            certifications=self.sample_certifications,
            client=mock_client,
        )

        self.assertEqual(roadmap.resume_id, 1)
        self.assertEqual(roadmap.target_role_id, 5)
        self.assertEqual(roadmap.target_role_title, "Backend Software Engineer")
        self.assertEqual(roadmap.total_phases, 2)
        self.assertEqual(roadmap.total_items, 3)
        self.assertEqual(len(roadmap.phases), 2)

        # Verify phase 1 items are properly enriched with database URLs and titles
        phase1_items = roadmap.phases[0].items
        self.assertEqual(phase1_items[0].resource_id, 12)
        self.assertEqual(phase1_items[0].title, "FastAPI Async Web Development")
        self.assertEqual(phase1_items[0].url, "https://fastapi.tiangolo.com/tutorial/")
        self.assertTrue(phase1_items[0].is_free)

        # Verify phase 2 certification item is enriched
        phase2_items = roadmap.phases[1].items
        self.assertEqual(phase2_items[0].certification_id, 3)
        self.assertEqual(phase2_items[0].title, "AWS Certified Cloud Practitioner")
        self.assertEqual(phase2_items[0].platform_or_provider, "Amazon Web Services")
        self.assertEqual(phase2_items[0].url, "https://aws.amazon.com/certification/certified-cloud-practitioner/")

    def test_invalid_unsupplied_resource_id_rejected(self):
        """Gemini returning a resource_id not present in supplied resources is rejected."""
        mock_client = MagicMock()
        bad_payload = json.loads(json.dumps(self.valid_gemini_roadmap_payload))
        bad_payload["phases"][0]["items"][0]["resource_id"] = 999  # Not in [10, 12]

        mock_response = MagicMock()
        mock_response.text = json.dumps(bad_payload)
        mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Software Engineer",
                learning_resources=self.sample_resources,
                certifications=self.sample_certifications,
                client=mock_client,
            )
        self.assertIn("unapproved or non-existent resource_id: 999", str(ctx.exception))

    def test_invalid_unsupplied_certification_id_rejected(self):
        """Gemini returning a certification_id not present in supplied certifications is rejected."""
        mock_client = MagicMock()
        bad_payload = json.loads(json.dumps(self.valid_gemini_roadmap_payload))
        bad_payload["phases"][1]["items"][0]["certification_id"] = 777  # Not in [3]

        mock_response = MagicMock()
        mock_response.text = json.dumps(bad_payload)
        mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Software Engineer",
                learning_resources=self.sample_resources,
                certifications=self.sample_certifications,
                client=mock_client,
            )
        self.assertIn("unapproved or non-existent certification_id: 777", str(ctx.exception))

    def test_malformed_gemini_response_raises_parsing_error(self):
        """Non-JSON or empty response from Gemini raises GeminiResponseParsingError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "NOT VALID JSON"
        mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Software Engineer",
                learning_resources=self.sample_resources,
                certifications=self.sample_certifications,
                client=mock_client,
            )
        self.assertIn("Invalid JSON returned by Gemini", str(ctx.exception))

    def test_empty_response_body_raises_parsing_error(self):
        """Empty text body raises GeminiResponseParsingError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Software Engineer",
                learning_resources=self.sample_resources,
                client=mock_client,
            )
        self.assertIn("empty response body", str(ctx.exception))

    def test_missing_api_key_raises_configuration_error(self):
        """Missing GEMINI_API_KEY raises GeminiConfigurationError."""
        with patch.object(settings, "GEMINI_API_KEY", None):
            with self.assertRaises(GeminiConfigurationError):
                generate_learning_roadmap(
                    resume_id=1,
                    target_role_title="Backend Software Engineer",
                    learning_resources=self.sample_resources,
                    client=None,
                )

    def test_gemini_quota_error_raised(self):
        """Gemini 429 quota exhaustion raises GeminiQuotaExceededError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = genai_errors.APIError(
            429, {"error": {"message": "Resource has been exhausted (e.g. check quota)."}}
        )

        with self.assertRaises(GeminiQuotaExceededError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Software Engineer",
                learning_resources=self.sample_resources,
                client=mock_client,
            )
        self.assertIn("quota exceeded", str(ctx.exception).lower())

    def test_gemini_network_error_raised(self):
        """Connection timeout raises GeminiNetworkError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Connection timed out after 30s")

        with self.assertRaises(GeminiNetworkError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Software Engineer",
                learning_resources=self.sample_resources,
                client=mock_client,
            )
        self.assertIn("network error", str(ctx.exception).lower())

    def test_privacy_protection_no_pii_in_prompt(self):
        """Verify candidate PII (name, email, phone) is scrubbed before prompt assembly."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(self.valid_gemini_roadmap_payload)
        mock_client.models.generate_content.return_value = mock_response

        generate_learning_roadmap(
            resume_id=1,
            target_role_title="Developer john.doe@email.com",
            verified_skills=["Python", "Phone: +1-555-555-5555"],
            missing_skills=["Docker", "Contact: john.doe@email.com"],
            learning_resources=self.sample_resources,
            certifications=self.sample_certifications,
            candidate_name="John Doe",
            client=mock_client,
        )

        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]

        self.assertNotIn("john.doe@email.com", contents)
        self.assertNotIn("+1-555-555-5555", contents)
        self.assertNotIn("John Doe", contents)
        self.assertIn("Docker", contents)
        self.assertIn("Python", contents)

    def test_empty_catalog_returns_empty_roadmap_without_llm_call(self):
        """When 0 resources and 0 certifications are supplied, return empty roadmap without calling Gemini."""
        mock_client = MagicMock()

        roadmap = generate_learning_roadmap(
            resume_id=5,
            target_role_title="Backend Engineer",
            learning_resources=[],
            certifications=[],
            client=mock_client,
        )

        mock_client.models.generate_content.assert_not_called()
        self.assertEqual(roadmap.total_phases, 0)
        self.assertEqual(roadmap.total_items, 0)
        self.assertEqual(len(roadmap.phases), 0)

    def test_simplified_gemini_roadmap_schema_structure(self):
        """
        Verify that build_gemini_response_schema(GeminiRoadmapOutput) produces a minimal schema
        without state-exploding constraints (no min_length, max_length, min_items, max_items, minimum, maximum).
        """
        schema = build_gemini_response_schema(GeminiRoadmapOutput)
        self.assertIsInstance(schema, genai_types.Schema)
        self.assertIsNone(schema.additional_properties)

        dumped = schema.model_dump(by_alias=True, exclude_none=True)
        dumped_json = json.dumps(dumped)

        # Confirm no additional_properties
        self.assertNotIn("additional_properties", dumped_json)
        self.assertNotIn("additionalProperties", dumped_json)

        # Confirm top-level properties are minimal (only summary and phases)
        top_props = dumped.get("properties", {})
        self.assertIn("phases", top_props)
        self.assertIn("summary", top_props)
        self.assertNotIn("resume_id", top_props)
        self.assertNotIn("target_role_id", top_props)
        self.assertNotIn("target_role_title", top_props)
        self.assertNotIn("total_phases", top_props)
        self.assertNotIn("total_items", top_props)
        self.assertNotIn("generated_at", top_props)

        # Confirm no state-exploding constraints in phases array items
        phase_items = top_props["phases"].get("items", {})
        self.assertNotIn("max_items", top_props["phases"])
        self.assertNotIn("min_items", top_props["phases"])

        phase_props = phase_items.get("properties", {})
        self.assertIn("phase_number", phase_props)
        self.assertIn("title", phase_props)
        self.assertIn("description", phase_props)
        self.assertIn("items", phase_props)
        self.assertNotIn("min_length", phase_props.get("title", {}))
        self.assertNotIn("max_length", phase_props.get("title", {}))
        self.assertNotIn("minimum", phase_props.get("phase_number", {}))

        # Confirm item properties in items array
        item_items = phase_props["items"].get("items", {})
        item_props = item_items.get("properties", {})
        self.assertIn("item_type", item_props)
        self.assertIn("resource_id", item_props)
        self.assertIn("certification_id", item_props)
        self.assertIn("personalized_explanation", item_props)
        self.assertNotIn("min_length", item_props.get("personalized_explanation", {}))
        self.assertNotIn("max_length", item_props.get("personalized_explanation", {}))
        self.assertNotIn("minimum", item_props.get("resource_id", {}))

    def test_simplified_payload_generation_and_normalization(self):
        """
        Verify that a minimal Gemini response containing ONLY phases and items
        (without top-level metadata or sequence numbers) is parsed, validated, and enriched correctly.
        """
        mock_client = MagicMock()
        minimal_payload = {
            "summary": "Core foundational skills roadmap.",
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Backend Essentials",
                    "description": "Learn FastAPI and Docker basics.",
                    "items": [
                        {
                            "item_type": "learning_resource",  # Lowercase test
                            "resource_id": 12,
                            "targeted_skill_name": "FastAPI",
                            "personalized_explanation": "Master async backend development to bridge required skills.",
                        },
                        {
                            "item_type": "LEARNING_RESOURCE",
                            "resource_id": 10,
                            "targeted_skill_name": "Docker",
                            "personalized_explanation": "Gain containerization proficiency for microservice deployment.",
                        },
                    ],
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(minimal_payload)
        mock_client.models.generate_content.return_value = mock_response

        roadmap = generate_learning_roadmap(
            resume_id=8,
            target_role_title="Backend Developer",
            target_role_id=2,
            learning_resources=self.sample_resources,
            certifications=self.sample_certifications,
            client=mock_client,
        )

        self.assertEqual(roadmap.resume_id, 8)
        self.assertEqual(roadmap.target_role_id, 2)
        self.assertEqual(roadmap.target_role_title, "Backend Developer")
        self.assertEqual(roadmap.total_phases, 1)
        self.assertEqual(roadmap.total_items, 2)
        self.assertEqual(len(roadmap.phases), 1)

        phase = roadmap.phases[0]
        self.assertEqual(phase.phase_number, 1)
        self.assertEqual(phase.title, "Backend Essentials")
        self.assertEqual(len(phase.items), 2)

        # Check item 1 enrichment and sequence order assignment
        item1 = phase.items[0]
        self.assertEqual(item1.item_type, RoadmapItemType.LEARNING_RESOURCE)
        self.assertEqual(item1.resource_id, 12)
        self.assertEqual(item1.title, "FastAPI Async Web Development")
        self.assertEqual(item1.sequence_order, 1)

        # Check item 2 enrichment
        item2 = phase.items[1]
        self.assertEqual(item2.item_type, RoadmapItemType.LEARNING_RESOURCE)
        self.assertEqual(item2.resource_id, 10)
        self.assertEqual(item2.title, "Official Docker Tutorial")
        self.assertEqual(item2.sequence_order, 2)

    def test_invalid_item_type_rejected(self):
        """Item with an unrecognized item_type (e.g. 'BOOK') is rejected."""
        mock_client = MagicMock()
        bad_payload = {
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Phase 1",
                    "description": "General description",
                    "items": [
                        {
                            "item_type": "UNSUPPORTED_TYPE",
                            "resource_id": 10,
                            "personalized_explanation": "Explanation for testing invalid type.",
                        }
                    ],
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(bad_payload)
        mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Developer",
                learning_resources=self.sample_resources,
                client=mock_client,
            )
        self.assertIn("Invalid item_type 'UNSUPPORTED_TYPE'", str(ctx.exception))

    def test_missing_required_resource_id_rejected(self):
        """LEARNING_RESOURCE without resource_id fails validation."""
        mock_client = MagicMock()
        bad_payload = {
            "phases": [
                {
                    "phase_number": 1,
                    "title": "Phase 1",
                    "description": "General description",
                    "items": [
                        {
                            "item_type": "LEARNING_RESOURCE",
                            "resource_id": None,
                            "personalized_explanation": "Missing required database ID for learning resource.",
                        }
                    ],
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(bad_payload)
        mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(GeminiResponseParsingError) as ctx:
            generate_learning_roadmap(
                resume_id=1,
                target_role_title="Backend Developer",
                learning_resources=self.sample_resources,
                client=mock_client,
            )
        self.assertIn("resource_id is required", str(ctx.exception))



if __name__ == "__main__":
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
