"""
Step 1: Tests for Gemini-Powered Personalized Learning Roadmap Schemas
Validates:
1. Strict schema constraints for learning roadmap items, phases, and response envelopes.
2. Requirement that each item references an existing database resource_id or certification_id.
3. Forbidding of unexpected fields (e.g. arbitrary URLs, invented titles, fake providers).
4. Mutual exclusivity of resource_id and certification_id based on item_type.
5. Gemini JSON schema compatibility (stripping additionalProperties).
6. Backward compatibility of existing recommendation schemas.
"""
import unittest
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.schemas.recommendation import (
    RoadmapItemType,
    RoadmapItem,
    RoadmapPhase,
    PersonalizedRoadmapResponse,
    LearningRoadmapResponse,
    EnrichedRoadmapItem,
    EnrichedRoadmapPhase,
    EnrichedLearningRoadmapResponse,
    ResourceRecommendationItem,
    CertificationRecommendationItem,
    ResumeConsolidatedRecommendationsResponse,
)


class TestPersonalizedRoadmapSchemas(unittest.TestCase):
    """Test suite for personalized learning roadmap Pydantic schemas."""

    def test_valid_learning_resource_item(self):
        """Valid learning resource item with valid resource_id passes validation."""
        item = RoadmapItem(
            item_type=RoadmapItemType.LEARNING_RESOURCE,
            resource_id=14,
            targeted_skill_id=5,
            targeted_skill_name="Docker",
            personalized_explanation="Docker is essential for containerizing applications. Since your profile already has Python experience, learning Docker will bridge your deployment gap.",
            sequence_order=1,
        )
        self.assertEqual(item.item_type, RoadmapItemType.LEARNING_RESOURCE)
        self.assertEqual(item.resource_id, 14)
        self.assertIsNone(item.certification_id)
        self.assertEqual(item.targeted_skill_name, "Docker")
        self.assertEqual(item.sequence_order, 1)

    def test_valid_certification_item(self):
        """Valid certification item with valid certification_id passes validation."""
        item = RoadmapItem(
            item_type=RoadmapItemType.CERTIFICATION,
            certification_id=3,
            targeted_skill_id=8,
            targeted_skill_name="AWS Cloud",
            personalized_explanation="Validating your cloud skills with an industry certification will demonstrate foundational infrastructure proficiency to employers.",
            sequence_order=2,
        )
        self.assertEqual(item.item_type, RoadmapItemType.CERTIFICATION)
        self.assertEqual(item.certification_id, 3)
        self.assertIsNone(item.resource_id)
        self.assertEqual(item.targeted_skill_name, "AWS Cloud")

    def test_learning_resource_missing_resource_id_raises(self):
        """LEARNING_RESOURCE without resource_id fails validation."""
        with self.assertRaises(ValidationError) as ctx:
            RoadmapItem(
                item_type=RoadmapItemType.LEARNING_RESOURCE,
                targeted_skill_name="Kubernetes",
                personalized_explanation="Essential for microservices orchestration.",
            )
        self.assertIn("resource_id is required", str(ctx.exception))

    def test_certification_missing_certification_id_raises(self):
        """CERTIFICATION without certification_id fails validation."""
        with self.assertRaises(ValidationError) as ctx:
            RoadmapItem(
                item_type=RoadmapItemType.CERTIFICATION,
                targeted_skill_name="Terraform",
                personalized_explanation="Validates infrastructure as code skills.",
            )
        self.assertIn("certification_id is required", str(ctx.exception))

    def test_item_with_both_ids_raises(self):
        """Providing both resource_id and certification_id raises validation error."""
        with self.assertRaises(ValidationError) as ctx:
            RoadmapItem(
                item_type=RoadmapItemType.LEARNING_RESOURCE,
                resource_id=10,
                certification_id=2,
                targeted_skill_name="SQL",
                personalized_explanation="Relational database skills are critical for backend development.",
            )
        self.assertIn("certification_id must not be provided", str(ctx.exception))

    def test_arbitrary_unwanted_fields_forbidden(self):
        """Unexpected arbitrary fields (e.g. invented URLs or titles) are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            RoadmapItem(
                item_type=RoadmapItemType.LEARNING_RESOURCE,
                resource_id=1,
                targeted_skill_name="Python",
                personalized_explanation="Foundational language skill.",
                invented_url="https://fake-course.com/python",  # Forbidden!
            )
        self.assertIn("extra_forbidden", str(ctx.exception))

    def test_explanation_length_bounds(self):
        """Personalized explanation must meet minimum and maximum length bounds."""
        # Too short (< 10 chars)
        with self.assertRaises(ValidationError):
            RoadmapItem(
                item_type=RoadmapItemType.LEARNING_RESOURCE,
                resource_id=1,
                targeted_skill_name="Git",
                personalized_explanation="Too short",
            )

        # Exceeds maximum (> 1000 chars)
        with self.assertRaises(ValidationError):
            RoadmapItem(
                item_type=RoadmapItemType.LEARNING_RESOURCE,
                resource_id=1,
                targeted_skill_name="Git",
                personalized_explanation="A" * 1001,
            )

    def test_valid_roadmap_phase(self):
        """RoadmapPhase groups items with title, phase_number, and description."""
        item1 = RoadmapItem(
            item_type=RoadmapItemType.LEARNING_RESOURCE,
            resource_id=5,
            targeted_skill_name="PostgreSQL",
            personalized_explanation="Essential for mastering relational schema design and indexing.",
            sequence_order=1,
        )
        item2 = RoadmapItem(
            item_type=RoadmapItemType.LEARNING_RESOURCE,
            resource_id=8,
            targeted_skill_name="Redis",
            personalized_explanation="Crucial for caching layers and high-performance throughput.",
            sequence_order=2,
        )
        phase = RoadmapPhase(
            phase_number=1,
            title="Phase 1: Database & Caching Core",
            description="Master primary persistence and caching layers needed for high-traffic web applications.",
            items=[item1, item2],
        )
        self.assertEqual(phase.phase_number, 1)
        self.assertEqual(len(phase.items), 2)
        self.assertEqual(phase.items[0].resource_id, 5)

    def test_valid_personalized_roadmap_response(self):
        """PersonalizedRoadmapResponse top-level envelope validates correctly."""
        item = RoadmapItem(
            item_type=RoadmapItemType.LEARNING_RESOURCE,
            resource_id=12,
            targeted_skill_name="FastAPI",
            personalized_explanation="Leverage modern Python async paradigms for high-speed microservices.",
            sequence_order=1,
        )
        phase = RoadmapPhase(
            phase_number=1,
            title="Phase 1: Backend Frameworks",
            description="Build robust asynchronous REST APIs.",
            items=[item],
        )
        response = PersonalizedRoadmapResponse(
            resume_id=42,
            target_role_id=1,
            target_role_title="Backend Developer",
            total_phases=1,
            total_items=1,
            phases=[phase],
            summary="Targeted progression focusing on backend async architecture.",
        )
        self.assertEqual(response.resume_id, 42)
        self.assertEqual(response.target_role_title, "Backend Developer")
        self.assertEqual(response.total_phases, 1)
        self.assertIsInstance(response.generated_at, datetime)
        # Verify alias
        self.assertIs(LearningRoadmapResponse, PersonalizedRoadmapResponse)

    def test_enriched_roadmap_item_and_response(self):
        """EnrichedRoadmapItem includes verified database metadata (URL, title, platform)."""
        enriched_item = EnrichedRoadmapItem(
            item_type=RoadmapItemType.LEARNING_RESOURCE,
            resource_id=7,
            targeted_skill_name="Docker",
            personalized_explanation="Hands-on containerization tutorials to bridge DevOps gaps.",
            sequence_order=1,
            title="Docker Getting Started Tutorial",
            platform_or_provider="Docker Docs",
            url="https://docs.docker.com/get-started/",
            difficulty_or_level="BEGINNER",
            is_free=True,
        )
        self.assertEqual(enriched_item.title, "Docker Getting Started Tutorial")
        self.assertEqual(enriched_item.url, "https://docs.docker.com/get-started/")
        self.assertTrue(enriched_item.is_free)

        enriched_phase = EnrichedRoadmapPhase(
            phase_number=1,
            title="Phase 1: Containerization",
            description="Foundation of container workflows.",
            items=[enriched_item],
        )
        enriched_resp = EnrichedLearningRoadmapResponse(
            resume_id=10,
            target_role_id=2,
            target_role_title="DevOps Engineer",
            total_phases=1,
            total_items=1,
            phases=[enriched_phase],
        )
        self.assertEqual(len(enriched_resp.phases), 1)
        self.assertEqual(enriched_resp.phases[0].items[0].url, "https://docs.docker.com/get-started/")

    def test_gemini_json_schema_compatibility(self):
        """JSON schemas generated for Gemini do not contain additionalProperties."""
        item_schema = RoadmapItem.model_json_schema()
        self.assertNotIn("additionalProperties", item_schema)

        phase_schema = RoadmapPhase.model_json_schema()
        self.assertNotIn("additionalProperties", phase_schema)

        response_schema = PersonalizedRoadmapResponse.model_json_schema()
        self.assertNotIn("additionalProperties", response_schema)

    def test_existing_recommendation_schemas_backward_compatible(self):
        """Existing recommendation schemas continue to function identically."""
        res_item = ResourceRecommendationItem(
            recommendation_id=1,
            session_id=10,
            resource_id=5,
            title="Official Python Tutorial",
            platform_name="Python.org",
            url="https://docs.python.org/3/tutorial/",
            resource_type="DOCUMENTATION",
            difficulty_level="BEGINNER",
            is_free=True,
            targeted_skill_id=2,
            targeted_skill_name="Python",
            gap_priority="CRITICAL_MISSING",
            priority_order=1,
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(res_item.title, "Official Python Tutorial")
        self.assertTrue(res_item.is_free)


if __name__ == "__main__":
    unittest.main()
