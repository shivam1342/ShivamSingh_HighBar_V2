"""
Unit tests for DataAgent
Tests subtask execution, metric analysis, and data operations
"""

import unittest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from src.agents.data_agent import DataAgent


class TestDataAgent(unittest.TestCase):
    """Test suite for DataAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "thresholds": {
                "underperformer": {
                    "ctr": 0.01,
                    "roas": 1.0
                }
            }
        }
        
        # Create sample DataFrame
        self.df = pd.DataFrame({
            "campaign_id": ["C1", "C2", "C3", "C4", "C5"],
            "impressions": [1000, 2000, 1500, 3000, 2500],
            "clicks": [10, 50, 15, 90, 25],
            "spend": [100, 200, 150, 300, 250],
            "revenue": [500, 1200, 300, 1800, 1000],
            "date": pd.date_range("2025-01-01", periods=5)
        })
        
        # Calculate metrics
        self.df["ctr"] = self.df["clicks"] / self.df["impressions"]
        self.df["roas"] = self.df["revenue"] / self.df["spend"]
        
        self.mock_logger = Mock()
        self.data_agent = DataAgent(self.df, self.config, self.mock_logger)

    def test_data_agent_initialization(self):
        """Test data agent initializes correctly"""
        self.assertIsNotNone(self.data_agent)
        self.assertEqual(len(self.data_agent.df), 5)
        self.assertIsNotNone(self.data_agent.drift_detector)

    def test_get_summary(self):
        """Test data summary generation"""
        summary = self.data_agent.get_summary()
        
        self.assertIn("num_campaigns", summary)
        self.assertIn("date_range", summary)
        self.assertIn("metrics_summary", summary)
        
        self.assertEqual(summary["num_campaigns"], 5)
        self.assertIn("ctr", summary["metrics_summary"])
        self.assertIn("roas", summary["metrics_summary"])

    def test_identify_underperformers_ctr(self):
        """Test identifying underperforming campaigns by CTR"""
        subtask = {
            "type": "identify_underperformers",
            "params": {"metric": "ctr", "threshold": 0.02}
        }
        
        result = self.data_agent.execute_subtask(subtask)
        
        self.assertIn("underperformers", result)
        self.assertIn("count", result)
        
        # C1 has CTR 0.01, C3 has 0.01 - should be underperformers
        self.assertGreaterEqual(result["count"], 2)

    def test_identify_underperformers_roas(self):
        """Test identifying underperforming campaigns by ROAS"""
        subtask = {
            "type": "identify_underperformers",
            "params": {"metric": "roas", "threshold": 5.0}
        }
        
        result = self.data_agent.execute_subtask(subtask)
        
        self.assertIn("underperformers", result)
        # C3 has ROAS 2.0 - should be underperformer
        self.assertGreaterEqual(result["count"], 1)

    def test_analyze_metric_trend(self):
        """Test metric trend analysis"""
        subtask = {
            "type": "analyze_metric_trend",
            "params": {"metric": "ctr", "days": 30}
        }
        
        result = self.data_agent.execute_subtask(subtask)
        
        self.assertIn("metric", result)
        self.assertIn("trend", result)
        self.assertEqual(result["metric"], "ctr")

    def test_segment_analysis(self):
        """Test segment analysis"""
        subtask = {
            "type": "segment_analysis",
            "params": {"dimension": "campaign_id", "metric": "roas"}
        }
        
        result = self.data_agent.execute_subtask(subtask)
        
        self.assertIn("segments", result)
        self.assertIn("metric", result)
        self.assertEqual(result["metric"], "roas")

    def test_execute_multiple_subtasks(self):
        """Test executing multiple subtasks"""
        subtasks = [
            {"type": "identify_underperformers", "params": {"metric": "ctr"}},
            {"type": "analyze_metric_trend", "params": {"metric": "roas", "days": 30}},
            {"type": "segment_analysis", "params": {"dimension": "campaign_id"}}
        ]
        
        results = self.data_agent.execute_subtasks(subtasks)
        
        self.assertEqual(len(results), 3)
        self.assertIsInstance(results, list)

    def test_get_context_for_insights(self):
        """Test context preparation for insights"""
        analysis_results = [
            {"underperformers": [{"campaign_id": "C1", "ctr": 0.01}], "count": 1},
            {"metric": "roas", "trend": "increasing"}
        ]
        
        context = self.data_agent.get_context_for_insights(analysis_results)
        
        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 0)

    def test_prepare_creative_inputs(self):
        """Test creative input preparation"""
        insights = [
            {
                "id": "insight_1",
                "category": "ctr_decline",
                "recommendation": "Refresh ad creative"
            }
        ]
        
        creative_inputs = self.data_agent.prepare_creative_inputs(insights)
        
        self.assertIn("insights", creative_inputs)
        self.assertEqual(len(creative_inputs["insights"]), 1)

    def test_invalid_subtask_type(self):
        """Test handling of invalid subtask type"""
        subtask = {
            "type": "invalid_type",
            "params": {}
        }
        
        with self.assertRaises(ValueError):
            self.data_agent.execute_subtask(subtask)

    def test_subtask_missing_params(self):
        """Test handling subtask with missing parameters"""
        subtask = {
            "type": "identify_underperformers",
            "params": {}  # Missing metric
        }
        
        # Should handle gracefully or use defaults
        result = self.data_agent.execute_subtask(subtask)
        self.assertIsNotNone(result)

    def test_empty_dataframe(self):
        """Test data agent with empty DataFrame"""
        empty_df = pd.DataFrame()
        agent = DataAgent(empty_df, self.config, self.mock_logger)
        
        summary = agent.get_summary()
        self.assertEqual(summary["num_campaigns"], 0)

    def test_drift_detection_integration(self):
        """Test drift detection is triggered"""
        # Drift detector should be called during initialization
        self.assertIsNotNone(self.data_agent.drift_detector)


class TestDataAgentEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {"thresholds": {"underperformer": {"ctr": 0.01}}}
        self.mock_logger = Mock()

    def test_missing_metric_column(self):
        """Test handling when metric column is missing"""
        df = pd.DataFrame({
            "campaign_id": ["C1", "C2"],
            "impressions": [1000, 2000]
            # Missing clicks, spend, revenue
        })
        
        agent = DataAgent(df, self.config, self.mock_logger)
        
        # Should handle missing columns gracefully
        summary = agent.get_summary()
        self.assertIsNotNone(summary)

    def test_zero_division_handling(self):
        """Test handling of zero division in metric calculations"""
        df = pd.DataFrame({
            "campaign_id": ["C1"],
            "impressions": [0],  # Zero impressions
            "clicks": [0],
            "spend": [0],
            "revenue": [100]
        })
        
        agent = DataAgent(df, self.config, self.mock_logger)
        
        # Should not crash on division by zero
        summary = agent.get_summary()
        self.assertIsNotNone(summary)

    def test_negative_values(self):
        """Test handling negative values in data"""
        df = pd.DataFrame({
            "campaign_id": ["C1"],
            "impressions": [1000],
            "clicks": [10],
            "spend": [100],
            "revenue": [-50]  # Negative revenue
        })
        
        agent = DataAgent(df, self.config, self.mock_logger)
        summary = agent.get_summary()
        
        # Should handle but may flag in validation
        self.assertIsNotNone(summary)


if __name__ == "__main__":
    unittest.main()
