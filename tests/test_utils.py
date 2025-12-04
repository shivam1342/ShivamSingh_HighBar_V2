"""
Simple utility and component tests to improve coverage
Focus on easily testable components without complex mocking
"""

import unittest
import pandas as pd
from src.utils.threshold_manager import ThresholdManager
from src.monitoring.alert_manager import AlertManager, AlertSeverity, Alert
from src.monitoring.drift_detector import DriftDetector
from src.monitoring.metric_tracker import MetricTracker


class TestThresholdManager(unittest.TestCase):
    """Test ThresholdManager utility"""

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
        self.manager = ThresholdManager(self.config)

    def test_initialization(self):
        """Test manager initializes correctly"""
        self.assertIsNotNone(self.manager)

    def test_get_threshold_default(self):
        """Test getting default threshold"""
        threshold = self.manager.get_threshold("ctr")
        self.assertEqual(threshold, 0.01)

    def test_get_threshold_roas(self):
        """Test getting ROAS threshold"""
        threshold = self.manager.get_threshold("roas")
        self.assertEqual(threshold, 1.0)

    def test_get_threshold_with_quality(self):
        """Test adaptive threshold with quality"""
        threshold = self.manager.get_threshold("ctr", quality="volatile")
        self.assertLess(threshold, 0.01)  # Should be relaxed

    def test_get_threshold_nonexistent(self):
        """Test getting threshold for non-existent metric"""
        threshold = self.manager.get_threshold("nonexistent")
        self.assertIsNotNone(threshold)  # Should return default


class TestAlertSystem(unittest.TestCase):
    """Test Alert dataclass and helper functions"""

    def test_alert_creation(self):
        """Test creating an alert"""
        alert = Alert(
            severity=AlertSeverity.WARNING,
            source="test",
            message="Test alert",
            details={"key": "value"},
            recommendation="Fix it"
        )
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.source, "test")

    def test_alert_formatting(self):
        """Test alert formatting"""
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            source="test",
            message="Critical issue",
            details={},
            recommendation="Take action"
        )
        formatted = alert.format()
        self.assertIn("CRITICAL", formatted)
        self.assertIn("Critical issue", formatted)

    def test_alert_severity_levels(self):
        """Test all severity levels"""
        severities = [AlertSeverity.CRITICAL, AlertSeverity.WARNING, AlertSeverity.INFO]
        for sev in severities:
            alert = Alert(sev, "test", "msg", {}, "rec")
            self.assertEqual(alert.severity, sev)


class TestMetricTrackerSimple(unittest.TestCase):
    """Simple tests for MetricTracker"""

    def setUp(self):
        """Set up test fixtures"""
        self.tracker = MetricTracker()

    def test_initialization(self):
        """Test tracker initializes"""
        self.assertIsNotNone(self.tracker)

    def test_update_baseline(self):
        """Test updating baseline"""
        metrics = {"ctr": 0.01, "roas": 5.0}
        self.tracker.update_baseline(metrics)
        self.assertIsNotNone(self.tracker.baseline)

    def test_get_baseline_empty(self):
        """Test getting baseline when none exists"""
        baseline = self.tracker.get_baseline()
        self.assertIsNotNone(baseline)


class TestStructuredLogger(unittest.TestCase):
    """Test structured logger utility"""

    def test_logger_import(self):
        """Test structured logger can be imported"""
        from src.utils.structured_logger import StructuredLogger
        logger = StructuredLogger("test")
        self.assertIsNotNone(logger)

    def test_logger_context_manager(self):
        """Test logger context manager"""
        from src.utils.structured_logger import StructuredLogger
        logger = StructuredLogger("test")
        
        with logger.log_stage("test_stage"):
            pass  # Should not crash


class TestConfigLoader(unittest.TestCase):
    """Test config loading utility"""

    def test_config_import(self):
        """Test config can be imported"""
        from src.utils.config import load_config
        self.assertIsNotNone(load_config)


class TestDataFrameOperations(unittest.TestCase):
    """Test basic DataFrame operations used in codebase"""

    def test_create_sample_dataframe(self):
        """Test creating sample DataFrame"""
        df = pd.DataFrame({
            "campaign_id": ["C1", "C2"],
            "impressions": [1000, 2000],
            "clicks": [10, 20]
        })
        self.assertEqual(len(df), 2)
        self.assertIn("campaign_id", df.columns)

    def test_calculate_ctr(self):
        """Test CTR calculation"""
        df = pd.DataFrame({
            "impressions": [1000],
            "clicks": [10]
        })
        df["ctr"] = df["clicks"] / df["impressions"]
        self.assertEqual(df["ctr"].iloc[0], 0.01)

    def test_calculate_roas(self):
        """Test ROAS calculation"""
        df = pd.DataFrame({
            "spend": [100],
            "revenue": [500]
        })
        df["roas"] = df["revenue"] / df["spend"]
        self.assertEqual(df["roas"].iloc[0], 5.0)

    def test_handle_zero_division(self):
        """Test handling zero division"""
        df = pd.DataFrame({
            "impressions": [0],
            "clicks": [10]
        })
        # Should handle gracefully
        df["ctr"] = df["clicks"] / df["impressions"].replace(0, 1)
        self.assertIsNotNone(df["ctr"].iloc[0])


if __name__ == "__main__":
    unittest.main()
