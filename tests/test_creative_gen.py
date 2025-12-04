"""
Unit tests for CreativeGenerator
Tests creative recommendation generation and variations
"""

import unittest
from unittest.mock import Mock
from src.agents.creative_gen import CreativeGeneratorAgent
from src.utils.llm import LLMClient


class TestCreativeGenerator(unittest.TestCase):
    """Test suite for CreativeGeneratorAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm = Mock(spec=LLMClient)
        self.mock_logger = Mock()
        
        self.creative_gen = CreativeGeneratorAgent(
            llm_client=self.mock_llm,
            structured_logger=self.mock_logger
        )

    def test_creative_generator_initialization(self):
        """Test creative generator initializes correctly"""
        self.assertIsNotNone(self.creative_gen)
        self.assertEqual(self.creative_gen.llm_client, self.mock_llm)

    def test_generate_creatives_success(self):
        """Test successful creative generation"""
        mock_response = {
            "creatives": [
                {
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": "image_ad",
                    "headline": "Refresh Your Look",
                    "body": "Discover new styles",
                    "cta": "Shop Now",
                    "variations": [
                        {
                            "variation_id": "v1",
                            "headline": "Transform Your Style",
                            "body": "Explore trending designs"
                        },
                        {
                            "variation_id": "v2",
                            "headline": "Upgrade Your Wardrobe",
                            "body": "Find your perfect fit"
                        }
                    ],
                    "rationale": "Creative fatigue suggests need for refresh"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = [
            {
                "id": "insight_1",
                "category": "creative_fatigue",
                "recommendation": "Refresh ad creative"
            }
        ]
        creative_inputs = {"insights": insights}
        
        creatives = self.creative_gen.generate_creatives(insights, creative_inputs)
        
        self.assertEqual(len(creatives), 1)
        self.assertEqual(creatives[0]["id"], "creative_1")
        self.assertEqual(creatives[0]["creative_type"], "image_ad")
        self.assertEqual(len(creatives[0]["variations"]), 2)
        
        # Verify LLM was called
        self.mock_llm.generate_structured.assert_called_once()

    def test_generate_multiple_creatives(self):
        """Test generating multiple creative recommendations"""
        mock_response = {
            "creatives": [
                {
                    "id": f"creative_{i}",
                    "insight_id": f"insight_{i}",
                    "creative_type": "image_ad",
                    "headline": f"Headline {i}",
                    "body": f"Body {i}",
                    "cta": "Shop Now",
                    "variations": [],
                    "rationale": f"Rationale {i}"
                }
                for i in range(3)
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = [
            {"id": f"insight_{i}", "category": "test", "recommendation": "test"}
            for i in range(3)
        ]
        
        creatives = self.creative_gen.generate_creatives(insights, {})
        
        self.assertEqual(len(creatives), 3)
        for i, creative in enumerate(creatives):
            self.assertEqual(creative["id"], f"creative_{i}")

    def test_generate_creatives_with_variations(self):
        """Test creative generation with multiple variations"""
        mock_response = {
            "creatives": [
                {
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": "video_ad",
                    "headline": "Main Headline",
                    "body": "Main Body",
                    "cta": "Learn More",
                    "variations": [
                        {"variation_id": "v1", "headline": "Alt 1", "body": "Body 1"},
                        {"variation_id": "v2", "headline": "Alt 2", "body": "Body 2"},
                        {"variation_id": "v3", "headline": "Alt 3", "body": "Body 3"}
                    ],
                    "rationale": "Testing variations"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = [{"id": "insight_1", "recommendation": "test"}]
        creatives = self.creative_gen.generate_creatives(insights, {})
        
        self.assertEqual(len(creatives[0]["variations"]), 3)

    def test_generate_creatives_empty_insights(self):
        """Test creative generation with no insights"""
        mock_response = {"creatives": []}
        self.mock_llm.generate_structured.return_value = mock_response
        
        creatives = self.creative_gen.generate_creatives([], {})
        
        self.assertEqual(len(creatives), 0)

    def test_generate_creatives_llm_error(self):
        """Test handling of LLM errors"""
        self.mock_llm.generate_structured.side_effect = Exception("LLM API error")
        
        insights = [{"id": "insight_1"}]
        
        with self.assertRaises(Exception):
            self.creative_gen.generate_creatives(insights, {})

    def test_creative_types(self):
        """Test different creative types"""
        creative_types = ["image_ad", "video_ad", "carousel_ad", "collection_ad"]
        
        for creative_type in creative_types:
            mock_response = {
                "creatives": [{
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": creative_type,
                    "headline": "Test",
                    "body": "Test",
                    "cta": "Test",
                    "variations": [],
                    "rationale": "Test"
                }]
            }
            self.mock_llm.generate_structured.return_value = mock_response
            
            insights = [{"id": "insight_1"}]
            creatives = self.creative_gen.generate_creatives(insights, {})
            
            self.assertEqual(creatives[0]["creative_type"], creative_type)

    def test_creative_with_targeting_suggestions(self):
        """Test creative with targeting recommendations"""
        mock_response = {
            "creatives": [
                {
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": "image_ad",
                    "headline": "Target Audience",
                    "body": "Reach the right people",
                    "cta": "Shop",
                    "variations": [],
                    "rationale": "Based on audience data",
                    "targeting_suggestions": {
                        "age_range": "25-45",
                        "interests": ["fashion", "shopping"],
                        "platforms": ["facebook", "instagram"]
                    }
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = [{"id": "insight_1"}]
        creatives = self.creative_gen.generate_creatives(insights, {})
        
        self.assertIn("targeting_suggestions", creatives[0])

    def test_creative_rationale_quality(self):
        """Test that creatives include rationale"""
        mock_response = {
            "creatives": [
                {
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": "image_ad",
                    "headline": "Test",
                    "body": "Test",
                    "cta": "Test",
                    "variations": [],
                    "rationale": "Based on CTR decline, need fresh creative to combat fatigue"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = [{"id": "insight_1", "category": "ctr_decline"}]
        creatives = self.creative_gen.generate_creatives(insights, {})
        
        self.assertIn("rationale", creatives[0])
        self.assertGreater(len(creatives[0]["rationale"]), 10)


class TestCreativeGeneratorEdgeCases(unittest.TestCase):
    """Test edge cases for CreativeGenerator"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm = Mock(spec=LLMClient)
        self.mock_logger = Mock()

    def test_malformed_creative_response(self):
        """Test handling of malformed creative response"""
        self.mock_llm.generate_structured.return_value = {
            "creatives": [
                {
                    "id": "bad",
                    # Missing required fields
                }
            ]
        }
        
        gen = CreativeGeneratorAgent(self.mock_llm, self.mock_logger)
        insights = [{"id": "insight_1"}]
        
        # Should handle gracefully
        creatives = gen.generate_creatives(insights, {})
        self.assertIsInstance(creatives, list)

    def test_very_long_insight_text(self):
        """Test with very long insight text"""
        gen = CreativeGeneratorAgent(self.mock_llm, self.mock_logger)
        
        mock_response = {"creatives": []}
        self.mock_llm.generate_structured.return_value = mock_response
        
        # Create insight with very long text
        long_insight = {
            "id": "insight_1",
            "recommendation": "Test " * 1000
        }
        
        # Should handle without crashing
        creatives = gen.generate_creatives([long_insight], {})
        self.assertIsInstance(creatives, list)

    def test_creative_without_variations(self):
        """Test creative generation without variations"""
        mock_response = {
            "creatives": [
                {
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": "image_ad",
                    "headline": "Test",
                    "body": "Test",
                    "cta": "Test",
                    "variations": [],  # No variations
                    "rationale": "Test"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        gen = CreativeGeneratorAgent(self.mock_llm, self.mock_logger)
        insights = [{"id": "insight_1"}]
        creatives = gen.generate_creatives(insights, {})
        
        self.assertEqual(len(creatives[0]["variations"]), 0)


if __name__ == "__main__":
    unittest.main()
