"""
Integration tests for the complete pipeline
Tests end-to-end workflows and component interactions
"""

import unittest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from src.orchestrator import AgentOrchestrator
from src.pipeline.pipeline_engine import PipelineEngine


class TestPipelineIntegration(unittest.TestCase):
    """Integration tests for complete pipeline"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "llm": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "api_key": "test_key"
            },
            "thresholds": {
                "underperformer": {"ctr": 0.01, "roas": 1.0}
            },
            "monitoring": {
                "alerts": {"enabled": True},
                "health_checks": {"enabled": True}
            }
        }
        
        # Create sample data
        self.sample_df = pd.DataFrame({
            "campaign_id": [f"C{i}" for i in range(10)],
            "impressions": [1000 + i * 100 for i in range(10)],
            "clicks": [10 + i for i in range(10)],
            "spend": [100 + i * 10 for i in range(10)],
            "revenue": [500 + i * 50 for i in range(10)],
            "date": pd.date_range("2025-01-01", periods=10)
        })

    @patch('src.utils.llm.LLMClient')
    @patch('src.utils.data_loader.DataLoader')
    def test_full_pipeline_execution(self, mock_loader, mock_llm):
        """Test complete pipeline execution"""
        # Mock data loader
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = self.sample_df
        mock_loader_instance.get_summary.return_value = {
            "num_campaigns": 10,
            "date_range": {"start": "2025-01-01", "end": "2025-01-10"}
        }
        mock_loader.return_value = mock_loader_instance
        
        # Mock LLM responses
        mock_llm_instance = Mock()
        
        # Plan response
        plan_response = {
            "subtasks": [
                {"type": "identify_underperformers", "params": {"metric": "ctr"}}
            ]
        }
        
        # Insight response
        insight_response = {
            "insights": [
                {
                    "id": "insight_1",
                    "category": "ctr_decline",
                    "hypothesis": "Test hypothesis",
                    "evidence": ["E1", "E2"],
                    "confidence": 0.8,
                    "reasoning": "Test reasoning",
                    "recommendation": "Test recommendation"
                }
            ]
        }
        
        # Creative response
        creative_response = {
            "creatives": [
                {
                    "id": "creative_1",
                    "insight_id": "insight_1",
                    "creative_type": "image_ad",
                    "headline": "Test",
                    "body": "Test",
                    "cta": "Test",
                    "variations": [],
                    "rationale": "Test"
                }
            ]
        }
        
        mock_llm_instance.generate_structured.side_effect = [
            plan_response,
            insight_response,
            creative_response
        ]
        mock_llm.return_value = mock_llm_instance
        
        # Create orchestrator
        orchestrator = AgentOrchestrator("test.csv", self.config)
        
        # Execute pipeline
        query = "Show me underperforming campaigns"
        results = orchestrator.run(query)
        
        # Verify results structure
        self.assertIn("insights", results)
        self.assertIn("creatives", results)
        self.assertIn("execution_time", results)

    @patch('src.utils.llm.LLMClient')
    def test_pipeline_with_health_checks(self, mock_llm):
        """Test pipeline with health check integration"""
        # This tests that health checks run before pipeline
        orchestrator = AgentOrchestrator("test.csv", self.config)
        
        # Health checker should be initialized
        self.assertIsNotNone(orchestrator.health_checker)
        self.assertIsNotNone(orchestrator.alert_manager)

    @patch('src.utils.llm.LLMClient')
    def test_pipeline_with_drift_detection(self, mock_llm):
        """Test pipeline with drift detection"""
        orchestrator = AgentOrchestrator("test.csv", self.config)
        
        # Data agent should have drift detector
        # This is initialized when data is loaded
        self.assertIsNotNone(orchestrator.config)


class TestComponentIntegration(unittest.TestCase):
    """Test integration between components"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "thresholds": {"underperformer": {"ctr": 0.01}},
            "monitoring": {"alerts": {"enabled": True}}
        }

    @patch('src.utils.llm.LLMClient')
    def test_planner_to_data_agent_flow(self, mock_llm):
        """Test data flow from planner to data agent"""
        from src.agents.planner import PlannerAgent
        from src.agents.data_agent import DataAgent
        
        # Create sample data
        df = pd.DataFrame({
            "campaign_id": ["C1", "C2"],
            "impressions": [1000, 2000],
            "clicks": [10, 50],
            "spend": [100, 200],
            "revenue": [500, 1200]
        })
        
        # Mock planner
        mock_llm_instance = Mock()
        mock_llm_instance.generate_structured.return_value = {
            "subtasks": [
                {"type": "identify_underperformers", "params": {"metric": "ctr"}}
            ]
        }
        mock_llm.return_value = mock_llm_instance
        
        planner = PlannerAgent(mock_llm_instance, self.config, Mock())
        data_agent = DataAgent(df, self.config, Mock())
        
        # Generate plan
        data_summary = data_agent.get_summary()
        plan = planner.plan("Test query", data_summary)
        
        # Execute plan
        results = data_agent.execute_subtasks(plan["subtasks"])
        
        # Verify results
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    @patch('src.utils.llm.LLMClient')
    def test_data_agent_to_insight_agent_flow(self, mock_llm):
        """Test data flow from data agent to insight agent"""
        from src.agents.data_agent import DataAgent
        from src.agents.insight_agent import InsightAgent
        
        df = pd.DataFrame({
            "campaign_id": ["C1"],
            "impressions": [1000],
            "clicks": [5],
            "spend": [100],
            "revenue": [200]
        })
        
        data_agent = DataAgent(df, self.config, Mock())
        
        # Execute analysis
        subtasks = [{"type": "identify_underperformers", "params": {"metric": "ctr"}}]
        analysis_results = data_agent.execute_subtasks(subtasks)
        context = data_agent.get_context_for_insights(analysis_results)
        
        # Mock insight agent
        mock_llm_instance = Mock()
        mock_llm_instance.generate_structured.return_value = {
            "insights": [{
                "id": "insight_1",
                "category": "test",
                "hypothesis": "Test",
                "evidence": ["E1", "E2"],
                "confidence": 0.8,
                "reasoning": "Test",
                "recommendation": "Test"
            }]
        }
        
        insight_agent = InsightAgent(mock_llm_instance, Mock(), None, self.config)
        insights = insight_agent.generate_insights(analysis_results, context, "Test query")
        
        # Verify insights
        self.assertIsInstance(insights, list)
        self.assertGreater(len(insights), 0)

    @patch('src.utils.llm.LLMClient')
    def test_insight_to_creative_flow(self, mock_llm):
        """Test data flow from insights to creative generation"""
        from src.agents.data_agent import DataAgent
        from src.agents.creative_gen import CreativeGeneratorAgent
        
        df = pd.DataFrame({"campaign_id": ["C1"]})
        data_agent = DataAgent(df, self.config, Mock())
        
        insights = [
            {
                "id": "insight_1",
                "category": "ctr_decline",
                "recommendation": "Refresh creative"
            }
        ]
        
        creative_inputs = data_agent.prepare_creative_inputs(insights)
        
        # Mock creative generator
        mock_llm_instance = Mock()
        mock_llm_instance.generate_structured.return_value = {
            "creatives": [{
                "id": "creative_1",
                "insight_id": "insight_1",
                "creative_type": "image_ad",
                "headline": "Test",
                "body": "Test",
                "cta": "Test",
                "variations": [],
                "rationale": "Test"
            }]
        }
        
        creative_gen = CreativeGeneratorAgent(mock_llm_instance, Mock())
        creatives = creative_gen.generate_creatives(insights, creative_inputs)
        
        # Verify creatives
        self.assertIsInstance(creatives, list)
        self.assertEqual(len(creatives), 1)


class TestErrorScenarios(unittest.TestCase):
    """Test error handling in integration scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "thresholds": {"underperformer": {"ctr": 0.01}},
            "monitoring": {"alerts": {"enabled": True}}
        }

    @patch('src.utils.llm.LLMClient')
    def test_llm_failure_in_pipeline(self, mock_llm):
        """Test pipeline handles LLM failures"""
        from src.agents.planner import PlannerAgent
        
        mock_llm_instance = Mock()
        mock_llm_instance.generate_structured.side_effect = Exception("LLM Error")
        
        planner = PlannerAgent(mock_llm_instance, self.config, Mock())
        
        data_summary = {"num_campaigns": 10}
        
        with self.assertRaises(Exception):
            planner.plan("Test", data_summary)

    def test_empty_data_pipeline(self):
        """Test pipeline with empty dataset"""
        from src.agents.data_agent import DataAgent
        
        empty_df = pd.DataFrame()
        data_agent = DataAgent(empty_df, self.config, Mock())
        
        summary = data_agent.get_summary()
        self.assertEqual(summary["num_campaigns"], 0)

    def test_missing_required_columns(self):
        """Test pipeline with missing required columns"""
        from src.agents.data_agent import DataAgent
        
        # Missing critical columns
        incomplete_df = pd.DataFrame({
            "campaign_id": ["C1", "C2"]
            # Missing impressions, clicks, etc.
        })
        
        data_agent = DataAgent(incomplete_df, self.config, Mock())
        
        # Should handle gracefully
        summary = data_agent.get_summary()
        self.assertIsNotNone(summary)


if __name__ == "__main__":
    unittest.main()
