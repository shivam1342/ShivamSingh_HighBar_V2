"""
Tests for alerting system (AlertManager and HealthChecker).

Tests cover:
1. AlertManager: alert creation, filtering, deduplication, summary
2. HealthChecker: all 5 health check types (freshness, completeness, validity, schema, ranges)
3. Agent integration: low confidence alerts, quality alerts
4. Edge cases: empty data, missing columns, extreme values
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.monitoring.alert_manager import AlertManager, Alert, AlertSeverity
from src.monitoring.health_checker import HealthChecker, HealthCheckResult


class TestAlertManager(unittest.TestCase):
    """Test AlertManager functionality"""
    
    def setUp(self):
        """Create test config and alert manager"""
        self.config = {
            "monitoring": {
                "alerts": {
                    "enabled": True,
                    "confidence_threshold": 0.5,
                    "quality_threshold": 0.6
                }
            }
        }
        self.alert_manager = AlertManager(self.config)
    
    def test_add_alert(self):
        """Test adding generic alert"""
        self.alert_manager.add_alert(
            severity=AlertSeverity.WARNING,
            source="test",
            message="Test alert",
            details={"test_key": "test_value"}
        )
        
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, AlertSeverity.WARNING)
        self.assertEqual(alerts[0].source, "test")
        self.assertEqual(alerts[0].message, "Test alert")
    
    def test_add_low_confidence_alert(self):
        """Test adding low confidence alert"""
        self.alert_manager.add_low_confidence_alert(
            insight_id="test_insight",
            confidence=0.3,
            threshold=0.5,
            reason="Insufficient evidence"
        )
        
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, AlertSeverity.WARNING)
        self.assertEqual(alerts[0].source, "insight_agent")
        self.assertIn("low confidence", alerts[0].message)
    
    def test_add_quality_alert(self):
        """Test adding quality score alert"""
        # Test WARNING level (quality 0.5, threshold 0.6)
        self.alert_manager.add_quality_alert(
            quality_score=0.5,
            threshold=0.6,
            rejected_count=5,
            total_count=10
        )
        
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, AlertSeverity.WARNING)
        
        # Test CRITICAL level (quality 0.3, threshold 0.6)
        self.alert_manager.add_quality_alert(
            quality_score=0.3,
            threshold=0.6,
            rejected_count=7,
            total_count=10
        )
        
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[1].severity, AlertSeverity.CRITICAL)
    
    def test_add_missing_data_alert(self):
        """Test adding missing data alert"""
        self.alert_manager.add_missing_data_alert(
            days_missing=3,
            last_data_date="2024-01-01"
        )
        
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, AlertSeverity.CRITICAL)
        self.assertIn("No data in last", alerts[0].message)
    
    def test_add_data_freshness_alert(self):
        """Test adding data freshness alert"""
        self.alert_manager.add_data_freshness_alert(
            age_hours=72.0,
            threshold_hours=24
        )
        
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, AlertSeverity.WARNING)
        self.assertIn("Data is", alerts[0].message)
    
    def test_filter_by_severity(self):
        """Test filtering alerts by severity"""
        # Add alerts with different severities
        self.alert_manager.add_alert(AlertSeverity.INFO, "test", "Info alert")
        self.alert_manager.add_alert(AlertSeverity.WARNING, "test", "Warning alert")
        self.alert_manager.add_alert(AlertSeverity.CRITICAL, "test", "Critical alert")
        
        # Filter by severity
        critical = self.alert_manager.get_alerts(severity=AlertSeverity.CRITICAL)
        warnings = self.alert_manager.get_alerts(severity=AlertSeverity.WARNING)
        info = self.alert_manager.get_alerts(severity=AlertSeverity.INFO)
        
        self.assertEqual(len(critical), 1)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(info), 1)
    
    def test_filter_by_source(self):
        """Test filtering alerts by source"""
        self.alert_manager.add_alert(AlertSeverity.INFO, "source1", "Alert 1")
        self.alert_manager.add_alert(AlertSeverity.INFO, "source2", "Alert 2")
        self.alert_manager.add_alert(AlertSeverity.INFO, "source1", "Alert 3")
        
        source1_alerts = self.alert_manager.get_alerts(source="source1")
        source2_alerts = self.alert_manager.get_alerts(source="source2")
        
        self.assertEqual(len(source1_alerts), 2)
        self.assertEqual(len(source2_alerts), 1)
    
    def test_alert_deduplication(self):
        """Test that duplicate alerts create separate entries"""
        # Add same alert twice (both will be added as separate alerts)
        self.alert_manager.add_low_confidence_alert(
            insight_id="test_insight",
            confidence=0.3,
            threshold=0.5,
            reason="Test reason"
        )
        self.alert_manager.add_low_confidence_alert(
            insight_id="test_insight",
            confidence=0.3,
            threshold=0.5,
            reason="Test reason"
        )
        
        # Both alerts should be added (AlertManager doesn't prevent duplicates)
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 2)
    
    def test_get_summary(self):
        """Test alert summary generation"""
        self.alert_manager.add_alert(AlertSeverity.INFO, "test", "Info 1")
        self.alert_manager.add_alert(AlertSeverity.WARNING, "test", "Warning 1")
        self.alert_manager.add_alert(AlertSeverity.CRITICAL, "test", "Critical 1")
        self.alert_manager.add_alert(AlertSeverity.CRITICAL, "test", "Critical 2")
        
        summary = self.alert_manager.get_summary()
        
        self.assertEqual(summary["total_alerts"], 4)
        self.assertEqual(summary["critical_count"], 2)
        self.assertEqual(summary["warning_count"], 1)
        self.assertEqual(summary["info_count"], 1)
    
    def test_clear_alerts(self):
        """Test clearing all alerts"""
        self.alert_manager.add_alert(AlertSeverity.INFO, "test", "Test")
        self.alert_manager.add_alert(AlertSeverity.WARNING, "test", "Test")
        
        self.assertEqual(len(self.alert_manager.get_alerts()), 2)
        
        self.alert_manager.clear_alerts()
        self.assertEqual(len(self.alert_manager.get_alerts()), 0)
    
    def test_alert_history_limit(self):
        """Test that alert history is not limited in alerts list"""
        # Add 150 alerts
        for i in range(150):
            self.alert_manager.add_alert(
                AlertSeverity.INFO,
                "test",
                f"Alert {i}"
            )
        
        # All 150 alerts should be in alerts list
        alerts = self.alert_manager.get_alerts()
        self.assertEqual(len(alerts), 150)


class TestHealthChecker(unittest.TestCase):
    """Test HealthChecker functionality"""
    
    def setUp(self):
        """Create test config and sample data"""
        self.config = {
            "monitoring": {
                "health_checks": {
                    "enabled": True,
                    "max_data_age_hours": 24,
                    "max_missing_pct": 5,
                    "required_columns": ["campaign_id", "ad_id", "impressions", "clicks", "spend", "date"],
                    "metric_ranges": {
                        "roas_max_warning": 1000,
                        "ctr_max_warning": 50,
                        "spend_max_warning": 100000
                    }
                }
            }
        }
        
        # Create sample DataFrame
        self.df = pd.DataFrame({
            "campaign_id": ["c1", "c2", "c3", "c4", "c5"],
            "ad_id": ["a1", "a2", "a3", "a4", "a5"],
            "impressions": [1000, 2000, 3000, 4000, 5000],
            "clicks": [10, 20, 30, 40, 50],
            "spend": [100, 200, 300, 400, 500],
            "conversions": [5, 10, 15, 20, 25],
            "revenue": [500, 1000, 1500, 2000, 2500],
            "date": pd.to_datetime([
                datetime.now().strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d")
            ])
        })
        
        self.alert_manager = AlertManager(self.config)
    
    def test_check_data_freshness_pass(self):
        """Test data freshness check with fresh data"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        data_summary = {
            "date_range": {"end": datetime.now().strftime("%Y-%m-%d")}
        }
        health_checker._check_data_freshness(data_summary)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertTrue(health_checker.results[0].passed)
        self.assertEqual(health_checker.results[0].check_name, "data_freshness")
    
    def test_check_data_freshness_fail(self):
        """Test data freshness check with stale data"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        old_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        data_summary = {
            "date_range": {"end": old_date}
        }
        health_checker._check_data_freshness(data_summary)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
        self.assertEqual(health_checker.results[0].severity, AlertSeverity.WARNING)
    
    def test_check_data_completeness_pass(self):
        """Test data completeness check with complete data"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_data_completeness(self.df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertTrue(health_checker.results[0].passed)
    
    def test_check_data_completeness_fail(self):
        """Test data completeness check with missing values"""
        # Create DataFrame with missing values (>5%)
        incomplete_df = self.df.copy()
        incomplete_df.loc[0:2, "impressions"] = np.nan  # 60% missing
        
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_data_completeness(incomplete_df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
        self.assertEqual(health_checker.results[0].severity, AlertSeverity.CRITICAL)
    
    def test_check_data_validity_pass(self):
        """Test data validity check with valid data"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_data_validity(self.df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertTrue(health_checker.results[0].passed)
    
    def test_check_data_validity_fail_negatives(self):
        """Test data validity check with negative values"""
        invalid_df = self.df.copy()
        invalid_df.loc[0, "impressions"] = -100
        
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_data_validity(invalid_df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
        self.assertEqual(health_checker.results[0].severity, AlertSeverity.CRITICAL)
    
    def test_check_data_validity_fail_zero_impressions(self):
        """Test data validity check with zero impressions but spend"""
        invalid_df = self.df.copy()
        invalid_df.loc[0, "impressions"] = 0
        invalid_df.loc[0, "spend"] = 100
        
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_data_validity(invalid_df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
    
    def test_check_schema_consistency_pass(self):
        """Test schema consistency check with all required columns"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        data_summary = {"column_names": list(self.df.columns)}
        health_checker._check_schema_consistency(data_summary)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertTrue(health_checker.results[0].passed)
    
    def test_check_schema_consistency_fail(self):
        """Test schema consistency check with missing columns"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        data_summary = {"column_names": ["impressions", "clicks"]}  # Missing required columns
        health_checker._check_schema_consistency(data_summary)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
        self.assertEqual(health_checker.results[0].severity, AlertSeverity.CRITICAL)
    
    def test_check_metric_ranges_pass(self):
        """Test metric ranges check with normal values"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_metric_ranges(self.df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertTrue(health_checker.results[0].passed)
    
    def test_check_metric_ranges_fail_roas(self):
        """Test metric ranges check with extreme ROAS"""
        extreme_df = self.df.copy()
        extreme_df.loc[0, "revenue"] = 200000  # ROAS = 2000
        
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_metric_ranges(extreme_df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
        self.assertEqual(health_checker.results[0].severity, AlertSeverity.WARNING)
    
    def test_check_metric_ranges_fail_ctr(self):
        """Test metric ranges check with extreme CTR"""
        extreme_df = self.df.copy()
        extreme_df.loc[0, "clicks"] = 600  # CTR = 60%
        
        health_checker = HealthChecker(self.config, self.alert_manager)
        health_checker._check_metric_ranges(extreme_df)
        
        self.assertEqual(len(health_checker.results), 1)
        self.assertFalse(health_checker.results[0].passed)
    
    def test_run_all_checks(self):
        """Test running all health checks"""
        health_checker = HealthChecker(self.config, self.alert_manager)
        data_summary = {
            "date_range": {"end": datetime.now().strftime("%Y-%m-%d")},
            "column_names": list(self.df.columns)
        }
        health_passed = health_checker.run_all_checks(self.df, data_summary)
        
        # All should pass with valid data
        self.assertTrue(health_passed)
    
    def test_run_all_checks_with_failures(self):
        """Test running all checks with multiple failures"""
        # Create DataFrame with multiple issues
        bad_df = self.df.copy()
        bad_df.loc[0, "impressions"] = -100  # Negative value
        bad_df.loc[1:2, "clicks"] = np.nan  # Missing values (40%)
        bad_df.loc[3, "revenue"] = 500000  # Extreme ROAS
        
        health_checker = HealthChecker(self.config, self.alert_manager)
        data_summary = {
            "date_range": {"end": datetime.now().strftime("%Y-%m-%d")},
            "column_names": list(bad_df.columns)
        }
        health_passed = health_checker.run_all_checks(bad_df, data_summary)
        
        # Should fail due to critical issues
        self.assertFalse(health_passed)


if __name__ == "__main__":
    unittest.main()
