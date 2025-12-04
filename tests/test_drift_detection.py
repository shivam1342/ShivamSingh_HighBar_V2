"""
Test suite for drift detection functionality.

Tests metric tracking, drift detection, and alert generation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

from src.monitoring.metric_tracker import MetricTracker
from src.monitoring.drift_detector import DriftDetector, DriftAlert


@pytest.fixture
def sample_data():
    """Create sample Facebook Ads data."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    
    return pd.DataFrame({
        'date': dates,
        'campaign': [f'Campaign_{i%10}' for i in range(100)],
        'roas': np.random.normal(2.5, 0.5, 100),
        'ctr': np.random.normal(0.02, 0.005, 100),
        'cvr': np.random.normal(0.04, 0.01, 100),
        'spend': np.random.normal(150, 30, 100),
        'impressions': np.random.randint(1000, 5000, 100),
        'clicks': np.random.randint(20, 100, 100),
        'purchases': np.random.randint(1, 10, 100),
        'revenue': np.random.normal(300, 100, 100)
    })


@pytest.fixture
def temp_baseline_path():
    """Create temporary path for baseline metrics."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def config():
    """Sample configuration for drift detector."""
    return {
        'monitoring': {
            'drift_detection': {
                'roas_drop_threshold': 0.5,
                'ctr_drop_threshold': 0.3,
                'cvr_drop_threshold': 0.3,
                'outlier_std_threshold': 3.0
            }
        }
    }


class TestMetricTracker:
    """Test MetricTracker functionality."""
    
    def test_calculate_baseline(self, sample_data, temp_baseline_path):
        """Test baseline calculation from data."""
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Check structure
        assert 'created_at' in baseline
        assert 'data_window' in baseline
        assert 'metrics' in baseline
        
        # Check metrics
        assert 'roas' in baseline['metrics']
        assert 'ctr' in baseline['metrics']
        assert 'cvr' in baseline['metrics']
        
        # Check roas statistics
        roas_stats = baseline['metrics']['roas']
        assert 'mean' in roas_stats
        assert 'std' in roas_stats
        assert 'median' in roas_stats
        assert 'p25' in roas_stats
        assert 'p75' in roas_stats
        
        # Verify values are reasonable
        assert 2.0 < roas_stats['mean'] < 3.0  # Should be around 2.5
        assert roas_stats['std'] > 0
        assert roas_stats['p25'] < roas_stats['median'] < roas_stats['p75']
    
    def test_save_and_load_baseline(self, sample_data, temp_baseline_path):
        """Test saving and loading baseline."""
        tracker = MetricTracker(temp_baseline_path)
        
        # Calculate and save
        baseline = tracker.calculate_baseline(sample_data)
        tracker.save_baseline(baseline)
        
        # Load and verify
        loaded_baseline = tracker.load_baseline()
        assert loaded_baseline is not None
        assert loaded_baseline['metrics']['roas']['mean'] == baseline['metrics']['roas']['mean']
    
    def test_load_nonexistent_baseline(self, temp_baseline_path):
        """Test loading baseline when file doesn't exist."""
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.load_baseline()
        assert baseline is None
    
    def test_update_baseline(self, sample_data, temp_baseline_path):
        """Test updating baseline with new data."""
        tracker = MetricTracker(temp_baseline_path)
        
        # Create initial baseline
        tracker.update_baseline(sample_data)
        
        # Modify data
        modified_data = sample_data.copy()
        modified_data['roas'] = modified_data['roas'] * 0.8  # Drop ROAS
        
        # Update baseline
        new_baseline = tracker.update_baseline(modified_data)
        
        # Verify new baseline reflects modified data
        assert new_baseline['metrics']['roas']['mean'] < 2.5
    
    def test_get_baseline_age_days(self, sample_data, temp_baseline_path):
        """Test calculating baseline age."""
        tracker = MetricTracker(temp_baseline_path)
        
        # No baseline
        assert tracker.get_baseline_age_days() is None
        
        # Create baseline
        tracker.update_baseline(sample_data)
        
        # Check age (should be ~0 days)
        age = tracker.get_baseline_age_days()
        assert age is not None
        assert age < 1.0  # Less than 1 day old


class TestDriftDetector:
    """Test DriftDetector functionality."""
    
    def test_no_drift_on_similar_data(self, sample_data, config, temp_baseline_path):
        """Test that no drift is detected when data is similar."""
        # Create baseline
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Create detector
        detector = DriftDetector(config)
        
        # Check for drift (should have no critical alerts)
        alerts = detector.detect_drift(sample_data, baseline)
        critical_alerts = [a for a in alerts if a.severity == 'CRITICAL']
        assert len(critical_alerts) == 0
    
    def test_detect_roas_drop(self, sample_data, config, temp_baseline_path):
        """Test detection of significant ROAS drop."""
        # Create baseline with normal ROAS
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Create drifted data (ROAS drops 60%)
        drifted_data = sample_data.copy()
        drifted_data['roas'] = drifted_data['roas'] * 0.4  # 60% drop
        
        # Detect drift
        detector = DriftDetector(config)
        alerts = detector.detect_drift(drifted_data, baseline)
        
        # Should have ROAS alert
        assert len(alerts) > 0
        roas_alerts = [a for a in alerts if a.metric == 'roas']
        assert len(roas_alerts) > 0
        
        # Check alert properties
        roas_alert = roas_alerts[0]
        assert roas_alert.severity == 'CRITICAL'
        assert roas_alert.change_pct < -50  # More than 50% drop
        assert roas_alert.affected_campaigns > 0
    
    def test_detect_ctr_drop(self, sample_data, config, temp_baseline_path):
        """Test detection of CTR drop."""
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Drop CTR by 40%
        drifted_data = sample_data.copy()
        drifted_data['ctr'] = drifted_data['ctr'] * 0.6
        
        detector = DriftDetector(config)
        alerts = detector.detect_drift(drifted_data, baseline)
        
        # Should detect CTR drift
        ctr_alerts = [a for a in alerts if a.metric == 'ctr']
        assert len(ctr_alerts) > 0
        assert ctr_alerts[0].severity in ['CRITICAL', 'WARNING']
    
    def test_detect_outliers(self, sample_data, config, temp_baseline_path):
        """Test outlier detection."""
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Add extreme outliers
        outlier_data = sample_data.copy()
        outlier_data.loc[0:4, 'roas'] = 15.0  # 5 extreme outliers
        
        detector = DriftDetector(config)
        alerts = detector.detect_drift(outlier_data, baseline)
        
        # Should detect outliers
        outlier_alerts = [a for a in alerts if 'outlier' in a.message.lower()]
        assert len(outlier_alerts) > 0
        assert outlier_alerts[0].affected_campaigns >= 5
    
    def test_metric_increase_warning(self, sample_data, config, temp_baseline_path):
        """Test warning on extreme metric increase (possible data quality issue)."""
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Increase ROAS by 150% (3x baseline threshold)
        increased_data = sample_data.copy()
        increased_data['roas'] = increased_data['roas'] * 2.5
        
        detector = DriftDetector(config)
        alerts = detector.detect_drift(increased_data, baseline)
        
        # Should have warning about increase
        roas_alerts = [a for a in alerts if a.metric == 'roas']
        assert len(roas_alerts) > 0
        assert any('increased' in a.message.lower() for a in roas_alerts)
    
    def test_alert_severity_levels(self, sample_data, config, temp_baseline_path):
        """Test that different drift magnitudes produce appropriate severities."""
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        detector = DriftDetector(config)
        
        # Test 60% drop (should be CRITICAL)
        critical_data = sample_data.copy()
        critical_data['roas'] = critical_data['roas'] * 0.4
        critical_alerts = detector.detect_drift(critical_data, baseline)
        critical_roas = [a for a in critical_alerts if a.metric == 'roas'][0]
        assert critical_roas.severity == 'CRITICAL'
        
        # Test 40% drop (should be WARNING or CRITICAL depending on threshold)
        warning_data = sample_data.copy()
        warning_data['cvr'] = warning_data['cvr'] * 0.6
        warning_alerts = detector.detect_drift(warning_data, baseline)
        cvr_alerts = [a for a in warning_alerts if a.metric == 'cvr']
        if cvr_alerts:  # May trigger based on threshold
            assert cvr_alerts[0].severity in ['WARNING', 'CRITICAL']
    
    def test_log_alerts(self, sample_data, config, temp_baseline_path, caplog):
        """Test alert logging functionality."""
        import logging
        caplog.set_level(logging.INFO)
        
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        
        # Create drift
        drifted_data = sample_data.copy()
        drifted_data['roas'] = drifted_data['roas'] * 0.4
        
        detector = DriftDetector(config)
        alerts = detector.detect_drift(drifted_data, baseline)
        detector.log_alerts(alerts)
        
        # Check that alerts were logged
        assert 'DRIFT DETECTION' in caplog.text
        assert 'ROAS' in caplog.text


class TestDriftAlert:
    """Test DriftAlert dataclass."""
    
    def test_alert_creation(self):
        """Test creating DriftAlert object."""
        alert = DriftAlert(
            metric='roas',
            severity='CRITICAL',
            baseline_value=2.5,
            current_value=1.2,
            change_pct=-52.0,
            affected_campaigns=100,
            message='ROAS dropped 52.0%',
            timestamp=datetime.now().isoformat()
        )
        
        assert alert.metric == 'roas'
        assert alert.severity == 'CRITICAL'
        assert alert.change_pct == -52.0
        assert alert.affected_campaigns == 100
    
    def test_alert_with_details(self):
        """Test DriftAlert with optional details."""
        alert = DriftAlert(
            metric='ctr',
            severity='WARNING',
            baseline_value=0.02,
            current_value=0.015,
            change_pct=-25.0,
            affected_campaigns=50,
            message='CTR dropped 25.0%',
            timestamp=datetime.now().isoformat(),
            details={'std': 0.005, 'median': 0.018}
        )
        
        assert alert.details is not None
        assert 'std' in alert.details
        assert alert.details['std'] == 0.005


class TestIntegration:
    """Integration tests combining tracker and detector."""
    
    def test_full_drift_detection_workflow(self, sample_data, config, temp_baseline_path):
        """Test complete workflow: baseline creation → drift detection."""
        # Step 1: Create baseline
        tracker = MetricTracker(temp_baseline_path)
        baseline = tracker.calculate_baseline(sample_data)
        tracker.save_baseline(baseline)
        
        # Step 2: Simulate time passing with data change
        new_data = sample_data.copy()
        new_data['date'] = new_data['date'] + pd.Timedelta(days=30)
        new_data['roas'] = new_data['roas'] * 0.5  # 50% drop
        
        # Step 3: Load baseline and detect drift
        loaded_baseline = tracker.load_baseline()
        detector = DriftDetector(config)
        alerts = detector.detect_drift(new_data, loaded_baseline)
        
        # Step 4: Verify drift detected
        assert len(alerts) > 0
        assert any(a.metric == 'roas' for a in alerts)
    
    def test_baseline_update_after_drift(self, sample_data, config, temp_baseline_path):
        """Test updating baseline after expected drift."""
        tracker = MetricTracker(temp_baseline_path)
        detector = DriftDetector(config)
        
        # Initial baseline
        baseline1 = tracker.calculate_baseline(sample_data)
        tracker.save_baseline(baseline1)
        
        # Drift occurs
        drifted_data = sample_data.copy()
        drifted_data['roas'] = drifted_data['roas'] * 0.6
        
        # Detect drift
        alerts = detector.detect_drift(drifted_data, baseline1)
        assert len(alerts) > 0
        
        # Update baseline (drift is now "normal")
        baseline2 = tracker.update_baseline(drifted_data)
        
        # Check against new baseline (should have no critical drift)
        new_alerts = detector.detect_drift(drifted_data, baseline2)
        critical_alerts = [a for a in new_alerts if a.severity == 'CRITICAL']
        assert len(critical_alerts) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
