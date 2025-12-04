"""
Unit tests for PlannerAgent
Tests query planning, task generation, and adaptive threshold logic
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.agents.planner import PlannerAgent
from src.utils.llm import LLMClient


class TestPlannerAgent(unittest.TestCase):
    """Test suite for PlannerAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "thresholds": {
                "underperformer": {
                    "ctr": 0.01,
                    "roas": 1.0,
                    "cvr": 0.02
                }
            },
            "adaptive_thresholds": {
                "enabled": True,
                "quality_multipliers": {
                    "stable": 1.0,
                    "volatile": 0.7,
                    "highly_volatile": 0.5
                }
            }
        }
        
        # Mock LLM client
        self.mock_llm = Mock(spec=LLMClient)
        self.mock_logger = Mock()
        
        self.planner = PlannerAgent(
            llm_client=self.mock_llm,
            config=self.config,
            structured_logger=self.mock_logger
        )

    def test_planner_initialization(self):
        """Test planner initializes with correct configuration"""
        self.assertIsNotNone(self.planner)
        self.assertEqual(self.planner.llm_client, self.mock_llm)
        self.assertIsNotNone(self.planner.threshold_manager)

    def test_plan_with_simple_query(self):
        """Test planning with simple query"""
        # Mock LLM response
        mock_response = {
            "subtasks": [
                {
                    "type": "identify_underperformers",
                    "params": {"metric": "ctr", "threshold": 0.01}
                },
                {
                    "type": "analyze_metric_trend",
                    "params": {"metric": "ctr", "days": 30}
                }
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        data_summary = {
            "num_campaigns": 100,
            "date_range": {"start": "2025-01-01", "end": "2025-03-31"},
            "metrics_summary": {
                "ctr": {"mean": 0.012, "std": 0.005},
                "roas": {"mean": 5.0, "std": 2.0}
            }
        }
        
        query = "Show me underperforming campaigns"
        plan = self.planner.plan(query, data_summary)
        
        # Verify plan structure
        self.assertIn("subtasks", plan)
        self.assertIn("thresholds", plan)
        self.assertIn("data_quality", plan)
        self.assertEqual(len(plan["subtasks"]), 2)
        
        # Verify LLM was called
        self.mock_llm.generate_structured.assert_called_once()

    def test_plan_with_volatile_data(self):
        """Test planning adapts thresholds for volatile data"""
        mock_response = {
            "subtasks": [
                {"type": "identify_underperformers", "params": {"metric": "ctr"}}
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        # High variance data
        data_summary = {
            "num_campaigns": 50,
            "date_range": {"start": "2025-01-01", "end": "2025-03-31"},
            "metrics_summary": {
                "ctr": {"mean": 0.01, "std": 0.015, "cv": 1.5},  # Very high CV
                "roas": {"mean": 5.0, "std": 8.0, "cv": 1.6}
            }
        }
        
        plan = self.planner.plan("Show me campaigns", data_summary)
        
        # Check that thresholds were adapted
        self.assertIn("data_quality", plan)
        self.assertIn("thresholds", plan)
        
        # Volatile data should have lower thresholds (relaxed)
        if "ctr_threshold" in plan["thresholds"]:
            # Should be less than default due to volatility
            self.assertLess(plan["thresholds"]["ctr_threshold"], 0.01)

    def test_plan_with_stable_data(self):
        """Test planning with stable data uses standard thresholds"""
        mock_response = {
            "subtasks": [
                {"type": "identify_underperformers", "params": {"metric": "roas"}}
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        # Low variance data
        data_summary = {
            "num_campaigns": 100,
            "date_range": {"start": "2025-01-01", "end": "2025-03-31"},
            "metrics_summary": {
                "ctr": {"mean": 0.01, "std": 0.001, "cv": 0.1},  # Low CV
                "roas": {"mean": 5.0, "std": 0.5, "cv": 0.1}
            }
        }
        
        plan = self.planner.plan("Analyze campaigns", data_summary)
        
        self.assertIn("data_quality", plan)
        # Stable data should have quality level reflecting stability
        quality = plan.get("data_quality", {}).get("quality_level", "")
        self.assertIn(quality, ["stable", "medium"])

    def test_plan_handles_llm_error(self):
        """Test planner handles LLM errors gracefully"""
        # Mock LLM error
        self.mock_llm.generate_structured.side_effect = Exception("LLM API error")
        
        data_summary = {
            "num_campaigns": 100,
            "metrics_summary": {
                "ctr": {"mean": 0.01, "std": 0.005}
            }
        }
        
        with self.assertRaises(Exception):
            self.planner.plan("Show campaigns", data_summary)

    def test_plan_with_empty_query(self):
        """Test planner handles empty query"""
        mock_response = {
            "subtasks": [
                {"type": "segment_analysis", "params": {}}
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        data_summary = {"num_campaigns": 50}
        
        plan = self.planner.plan("", data_summary)
        
        # Should still generate a plan
        self.assertIn("subtasks", plan)
        self.assertIsInstance(plan["subtasks"], list)

    def test_plan_generates_multiple_subtasks(self):
        """Test planner can generate multiple subtasks"""
        mock_response = {
            "subtasks": [
                {"type": "identify_underperformers", "params": {"metric": "ctr"}},
                {"type": "analyze_metric_trend", "params": {"metric": "ctr", "days": 30}},
                {"type": "segment_analysis", "params": {"dimension": "campaign"}},
                {"type": "identify_underperformers", "params": {"metric": "roas"}}
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        data_summary = {"num_campaigns": 100}
        plan = self.planner.plan("Comprehensive campaign analysis", data_summary)
        
        self.assertEqual(len(plan["subtasks"]), 4)
        
        # Verify different subtask types
        task_types = [task["type"] for task in plan["subtasks"]]
        self.assertIn("identify_underperformers", task_types)
        self.assertIn("analyze_metric_trend", task_types)
        self.assertIn("segment_analysis", task_types)

    def test_plan_with_specific_metric_query(self):
        """Test planner handles metric-specific queries"""
        mock_response = {
            "subtasks": [
                {"type": "analyze_metric_trend", "params": {"metric": "roas", "days": 90}}
            ]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        data_summary = {"num_campaigns": 100}
        plan = self.planner.plan("Show ROAS trends", data_summary)
        
        self.assertEqual(len(plan["subtasks"]), 1)
        self.assertEqual(plan["subtasks"][0]["type"], "analyze_metric_trend")
        self.assertEqual(plan["subtasks"][0]["params"]["metric"], "roas")

    def test_threshold_adaptation_disabled(self):
        """Test planner works when adaptive thresholds disabled"""
        config_no_adaptive = self.config.copy()
        config_no_adaptive["adaptive_thresholds"] = {"enabled": False}
        
        planner = PlannerAgent(
            llm_client=self.mock_llm,
            config=config_no_adaptive,
            structured_logger=self.mock_logger
        )
        
        mock_response = {
            "subtasks": [{"type": "identify_underperformers", "params": {}}]
        }
        self.mock_llm.generate_structured.return_value = mock_response
        
        data_summary = {
            "num_campaigns": 100,
            "metrics_summary": {
                "ctr": {"mean": 0.01, "std": 0.01, "cv": 1.0}
            }
        }
        
        plan = planner.plan("Show campaigns", data_summary)
        
        # Should still generate valid plan
        self.assertIn("subtasks", plan)
        self.assertIn("thresholds", plan)


if __name__ == "__main__":
    unittest.main()
