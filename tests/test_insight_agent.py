"""
Unit tests for InsightAgent
Tests insight generation, confidence scoring, and validation
"""

import unittest
from unittest.mock import Mock, MagicMock
from src.agents.insight_agent import InsightAgent
from src.utils.llm import LLMClient


class TestInsightAgent(unittest.TestCase):
    """Test suite for InsightAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "monitoring": {
                "alerts": {
                    "confidence_threshold": 0.5
                }
            }
        }
        
        self.mock_llm = Mock(spec=LLMClient)
        self.mock_logger = Mock()
        self.mock_alert_manager = Mock()
        
        self.insight_agent = InsightAgent(
            llm_client=self.mock_llm,
            structured_logger=self.mock_logger,
            alert_manager=self.mock_alert_manager,
            config=self.config
        )

    def test_insight_agent_initialization(self):
        """Test insight agent initializes correctly"""
        self.assertIsNotNone(self.insight_agent)
        self.assertEqual(self.insight_agent.llm_client, self.mock_llm)
        self.assertEqual(self.insight_agent.confidence_threshold, 0.5)

    def test_generate_insights_success(self):
        """Test successful insight generation"""
        mock_response = {
            "insights": [
                {
                    "id": "insight_1",
                    "category": "ctr_decline",
                    "hypothesis": "CTR declined due to creative fatigue",
                    "evidence": ["CTR decreased 15%", "Campaign running 60 days"],
                    "confidence": 0.8,
                    "reasoning": "Long campaign duration suggests fatigue",
                    "recommendation": "Refresh ad creative"
                },
                {
                    "id": "insight_2",
                    "category": "roas_improvement",
                    "hypothesis": "ROAS improved due to better targeting",
                    "evidence": ["ROAS increased 20%", "New audience segments"],
                    "confidence": 0.75,
                    "reasoning": "New targeting shows better performance",
                    "recommendation": "Expand to similar audiences"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        analysis_results = [
            {"underperformers": [{"campaign_id": "C1", "ctr": 0.008}]},
            {"metric": "roas", "trend": "increasing", "change_pct": 20}
        ]
        context = "Campaign data shows performance changes"
        query = "Analyze campaign performance"
        
        insights = self.insight_agent.generate_insights(analysis_results, context, query)
        
        self.assertEqual(len(insights), 2)
        self.assertEqual(insights[0]["id"], "insight_1")
        self.assertEqual(insights[0]["confidence"], 0.8)
        self.assertEqual(insights[1]["category"], "roas_improvement")
        
        # Verify LLM was called
        self.mock_llm.generate_structured.assert_called_once()

    def test_generate_insights_with_low_confidence(self):
        """Test insight generation with low confidence scores"""
        mock_response = {
            "insights": [
                {
                    "id": "insight_low",
                    "category": "unknown",
                    "hypothesis": "Something might be happening",
                    "evidence": ["Unclear pattern"],
                    "confidence": 0.3,  # Below threshold
                    "reasoning": "Not enough data",
                    "recommendation": "Monitor"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        analysis_results = [{"trend": "unclear"}]
        insights = self.insight_agent.generate_insights(analysis_results, "", "")
        
        # Low confidence insight should trigger alert
        self.mock_alert_manager.add_low_confidence_alert.assert_called()

    def test_generate_insights_with_insufficient_evidence(self):
        """Test insights with insufficient evidence"""
        mock_response = {
            "insights": [
                {
                    "id": "insight_weak",
                    "category": "ctr_decline",
                    "hypothesis": "CTR may be declining",
                    "evidence": ["One data point"],  # Only 1 evidence point
                    "confidence": 0.6,
                    "reasoning": "Limited evidence",
                    "recommendation": "Investigate further"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = self.insight_agent.generate_insights([], "", "")
        
        # Should trigger alert for insufficient evidence
        self.mock_alert_manager.add_low_confidence_alert.assert_called()

    def test_generate_insights_empty_results(self):
        """Test insight generation with empty analysis results"""
        mock_response = {"insights": []}
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = self.insight_agent.generate_insights([], "", "")
        
        self.assertEqual(len(insights), 0)

    def test_generate_insights_llm_error(self):
        """Test handling of LLM errors"""
        self.mock_llm.generate_structured.side_effect = Exception("LLM API error")
        
        with self.assertRaises(Exception):
            self.insight_agent.generate_insights([], "", "")

    def test_confidence_threshold_enforcement(self):
        """Test that confidence threshold is enforced"""
        mock_response = {
            "insights": [
                {
                    "id": "high_conf",
                    "category": "ctr_decline",
                    "hypothesis": "Clear CTR decline",
                    "evidence": ["Evidence 1", "Evidence 2", "Evidence 3"],
                    "confidence": 0.9,
                    "reasoning": "Strong evidence",
                    "recommendation": "Take action"
                },
                {
                    "id": "low_conf",
                    "category": "unknown",
                    "hypothesis": "Unclear pattern",
                    "evidence": ["Weak evidence"],
                    "confidence": 0.4,  # Below 0.5 threshold
                    "reasoning": "Uncertain",
                    "recommendation": "Monitor"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = self.insight_agent.generate_insights([], "", "")
        
        # Alert should be triggered for low confidence
        calls = self.mock_alert_manager.add_low_confidence_alert.call_args_list
        self.assertGreater(len(calls), 0)

    def test_no_alert_manager(self):
        """Test insight generation without alert manager"""
        agent = InsightAgent(
            llm_client=self.mock_llm,
            structured_logger=self.mock_logger,
            alert_manager=None,  # No alert manager
            config=self.config
        )
        
        mock_response = {
            "insights": [
                {
                    "id": "insight_1",
                    "category": "ctr_decline",
                    "hypothesis": "CTR declining",
                    "evidence": ["Evidence"],
                    "confidence": 0.3,  # Low
                    "reasoning": "Test",
                    "recommendation": "Test"
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        # Should not crash without alert manager
        insights = agent.generate_insights([], "", "")
        self.assertEqual(len(insights), 1)

    def test_insight_categories(self):
        """Test different insight categories"""
        categories = [
            "ctr_decline", "ctr_improvement",
            "roas_decline", "roas_improvement",
            "creative_fatigue", "audience_saturation",
            "budget_efficiency", "timing_optimization"
        ]
        
        for category in categories:
            mock_response = {
                "insights": [{
                    "id": f"insight_{category}",
                    "category": category,
                    "hypothesis": f"Testing {category}",
                    "evidence": ["E1", "E2"],
                    "confidence": 0.8,
                    "reasoning": "Test",
                    "recommendation": "Test action"
                }]
            }
            self.mock_llm.generate_structured.return_value = mock_response
            
            insights = self.insight_agent.generate_insights([], "", "")
            self.assertEqual(insights[0]["category"], category)

    def test_multiple_insights_generation(self):
        """Test generating multiple insights at once"""
        mock_response = {
            "insights": [
                {
                    "id": f"insight_{i}",
                    "category": "test",
                    "hypothesis": f"Hypothesis {i}",
                    "evidence": ["E1", "E2"],
                    "confidence": 0.7 + i * 0.05,
                    "reasoning": "Test",
                    "recommendation": "Test"
                }
                for i in range(5)
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        insights = self.insight_agent.generate_insights([], "", "")
        
        self.assertEqual(len(insights), 5)
        # Verify each insight has required fields
        for insight in insights:
            self.assertIn("id", insight)
            self.assertIn("confidence", insight)
            self.assertIn("hypothesis", insight)


class TestInsightAgentEdgeCases(unittest.TestCase):
    """Test edge cases for InsightAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm = Mock(spec=LLMClient)
        self.mock_logger = Mock()
        self.config = {}

    def test_malformed_llm_response(self):
        """Test handling of malformed LLM response"""
        self.mock_llm.generate_structured.return_value = {
            "insights": [
                {
                    "id": "bad",
                    # Missing required fields
                }
            ]
        }
        
        agent = InsightAgent(self.mock_llm, self.mock_logger, None, self.config)
        
        # Should handle gracefully
        insights = agent.generate_insights([], "", "")
        # May be empty or filtered out
        self.assertIsInstance(insights, list)

    def test_very_long_context(self):
        """Test with very long context string"""
        agent = InsightAgent(self.mock_llm, self.mock_logger, None, self.config)
        
        mock_response = {"insights": []}
        self.mock_llm.generate_structured.return_value = mock_response
        
        # Create very long context
        long_context = "Data " * 10000
        
        # Should handle without crashing
        insights = agent.generate_insights([], long_context, "")
        self.assertIsInstance(insights, list)


if __name__ == "__main__":
    unittest.main()
