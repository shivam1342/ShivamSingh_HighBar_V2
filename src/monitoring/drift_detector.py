"""
DriftDetector: Detects when metrics drift from historical baseline.

This module provides:
1. Comparison of current metrics to baseline
2. Detection of significant metric drops
3. Outlier detection using z-scores
4. Alert generation and logging
"""

import logging
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DriftAlert:
    """
    Represents a single drift detection alert.
    
    Contains all information about detected drift including
    severity, metric values, and affected campaigns.
    """
    metric: str              # Metric name (roas, ctr, etc.)
    severity: str            # INFO, WARNING, or CRITICAL
    baseline_value: float    # Historical baseline value
    current_value: float     # Current measured value
    change_pct: float        # Percentage change from baseline
    affected_campaigns: int  # Number of campaigns affected
    message: str             # Human-readable description
    timestamp: str           # ISO timestamp of detection
    details: Optional[Dict] = None  # Additional context


class DriftDetector:
    """
    Detects drift in key metrics by comparing current data to baseline.
    
    Uses statistical methods to identify:
    - Significant metric drops (e.g., ROAS down 50%)
    - Distribution shifts
    - Statistical outliers
    """
    
    def __init__(self, config: Dict):
        """
        Initialize DriftDetector with configuration.
        
        Args:
            config: Full application config dictionary
        """
        self.config = config
        monitoring_config = config.get('monitoring', {})
        drift_config = monitoring_config.get('drift_detection', {})
        
        # Thresholds for different metrics
        self.roas_threshold = drift_config.get('roas_drop_threshold', 0.5)  # 50% drop
        self.ctr_threshold = drift_config.get('ctr_drop_threshold', 0.3)    # 30% drop
        self.cvr_threshold = drift_config.get('cvr_drop_threshold', 0.3)    # 30% drop
        self.outlier_threshold = drift_config.get('outlier_std_threshold', 3.0)  # 3 std dev
        
        logger.debug(f"DriftDetector initialized with thresholds: "
                    f"ROAS={self.roas_threshold}, CTR={self.ctr_threshold}, "
                    f"CVR={self.cvr_threshold}, Outlier={self.outlier_threshold}")
    
    def detect_drift(
        self, 
        current_df: pd.DataFrame, 
        baseline: Dict
    ) -> List[DriftAlert]:
        """
        Compare current data to baseline and detect drift.
        
        Args:
            current_df: Current data to analyze
            baseline: Historical baseline from MetricTracker
        
        Returns:
            List of DriftAlert objects (empty if no drift detected)
        """
        alerts = []
        
        # Check each metric for drift
        metric_thresholds = {
            'roas': self.roas_threshold,
            'ctr': self.ctr_threshold,
            'cvr': self.cvr_threshold
        }
        
        for metric_name, threshold in metric_thresholds.items():
            if metric_name in baseline['metrics']:
                alert = self._check_metric_drift(
                    metric_name=metric_name,
                    current_df=current_df,
                    baseline=baseline,
                    threshold=threshold
                )
                if alert:
                    alerts.append(alert)
        
        # Check for outliers
        outlier_alerts = self._detect_outliers(current_df, baseline)
        alerts.extend(outlier_alerts)
        
        return alerts
    
    def _check_metric_drift(
        self,
        metric_name: str,
        current_df: pd.DataFrame,
        baseline: Dict,
        threshold: float
    ) -> Optional[DriftAlert]:
        """
        Check if a single metric has drifted significantly.
        
        Args:
            metric_name: Name of metric to check
            current_df: Current data
            baseline: Historical baseline
            threshold: Drift threshold (0.5 = 50% drop triggers alert)
        
        Returns:
            DriftAlert if drift detected, None otherwise
        """
        if metric_name not in current_df.columns:
            return None
        
        # Get baseline and current values
        baseline_mean = baseline['metrics'][metric_name]['mean']
        current_mean = current_df[metric_name].mean()
        
        # Calculate percentage change
        change_pct = (current_mean - baseline_mean) / baseline_mean
        
        # Check if drop exceeds threshold
        if change_pct < -threshold:  # Negative = drop
            # Count affected campaigns
            baseline_threshold_value = baseline_mean * (1 - threshold)
            affected = (current_df[metric_name] < baseline_threshold_value).sum()
            
            # Determine severity based on magnitude
            if abs(change_pct) > 0.7:  # >70% drop
                severity = 'CRITICAL'
            elif abs(change_pct) > 0.5:  # >50% drop
                severity = 'CRITICAL'
            else:
                severity = 'WARNING'
            
            return DriftAlert(
                metric=metric_name,
                severity=severity,
                baseline_value=baseline_mean,
                current_value=current_mean,
                change_pct=change_pct * 100,  # Convert to percentage
                affected_campaigns=int(affected),
                message=f"{metric_name.upper()} dropped {abs(change_pct)*100:.1f}%",
                timestamp=datetime.now().isoformat(),
                details={
                    'baseline_std': baseline['metrics'][metric_name]['std'],
                    'current_std': float(current_df[metric_name].std()),
                    'baseline_median': baseline['metrics'][metric_name]['median'],
                    'current_median': float(current_df[metric_name].median())
                }
            )
        
        # Check for significant increase (might indicate data quality issues)
        elif change_pct > threshold * 2:  # >100% increase (2x threshold)
            return DriftAlert(
                metric=metric_name,
                severity='WARNING',
                baseline_value=baseline_mean,
                current_value=current_mean,
                change_pct=change_pct * 100,
                affected_campaigns=0,
                message=f"{metric_name.upper()} increased {change_pct*100:.1f}% - verify data quality",
                timestamp=datetime.now().isoformat(),
                details={
                    'baseline_std': baseline['metrics'][metric_name]['std'],
                    'current_std': float(current_df[metric_name].std())
                }
            )
        
        return None
    
    def _detect_outliers(
        self, 
        df: pd.DataFrame, 
        baseline: Dict
    ) -> List[DriftAlert]:
        """
        Detect campaigns with anomalous metric values using z-scores.
        
        Z-score = (value - mean) / std
        Values with |z-score| > threshold are outliers.
        
        Args:
            df: Current data
            baseline: Historical baseline
        
        Returns:
            List of DriftAlert objects for outliers
        """
        alerts = []
        
        for metric in ['roas', 'ctr', 'cvr']:
            if metric not in baseline['metrics'] or metric not in df.columns:
                continue
            
            baseline_mean = baseline['metrics'][metric]['mean']
            baseline_std = baseline['metrics'][metric]['std']
            
            if baseline_std == 0:  # Avoid division by zero
                continue
            
            # Calculate z-scores for all campaigns
            z_scores = (df[metric] - baseline_mean) / baseline_std
            
            # Find outliers
            outliers = df[abs(z_scores) > self.outlier_threshold]
            
            if len(outliers) > 0:
                # Calculate outlier statistics
                num_outliers = len(outliers)
                pct_outliers = (num_outliers / len(df)) * 100
                
                # Determine severity based on percentage
                if pct_outliers > 10:  # >10% are outliers
                    severity = 'WARNING'
                else:
                    severity = 'INFO'
                
                alerts.append(DriftAlert(
                    metric=metric,
                    severity=severity,
                    baseline_value=baseline_mean,
                    current_value=float(outliers[metric].mean()),
                    change_pct=0.0,  # Not a drift, just outliers
                    affected_campaigns=num_outliers,
                    message=f"{num_outliers} campaigns ({pct_outliers:.1f}%) have outlier {metric.upper()} values",
                    timestamp=datetime.now().isoformat(),
                    details={
                        'max_z_score': float(abs(z_scores).max()),
                        'outlier_mean': float(outliers[metric].mean()),
                        'outlier_std': float(outliers[metric].std())
                    }
                ))
        
        return alerts
    
    def log_alerts(self, alerts: List[DriftAlert]) -> None:
        """
        Log drift alerts with formatted output.
        
        Args:
            alerts: List of DriftAlert objects to log
        """
        if not alerts:
            logger.info("✅ No drift detected - all metrics within normal range")
            return
        
        # Separate by severity
        critical_alerts = [a for a in alerts if a.severity == 'CRITICAL']
        warning_alerts = [a for a in alerts if a.severity == 'WARNING']
        info_alerts = [a for a in alerts if a.severity == 'INFO']
        
        logger.warning("=" * 70)
        logger.warning(f"🚨 DRIFT DETECTION: {len(alerts)} alert(s) found")
        logger.warning("=" * 70)
        
        # Log critical alerts first
        for alert in critical_alerts:
            logger.critical("")
            logger.critical(f"🚨 {alert.message}")
            logger.critical(f"   Metric:       {alert.metric.upper()}")
            logger.critical(f"   Baseline:     {alert.baseline_value:.3f}")
            logger.critical(f"   Current:      {alert.current_value:.3f}")
            logger.critical(f"   Change:       {alert.change_pct:+.1f}%")
            logger.critical(f"   Affected:     {alert.affected_campaigns} campaigns")
            
            if alert.details:
                logger.critical(f"   Baseline Med: {alert.details.get('baseline_median', 'N/A')}")
                logger.critical(f"   Current Med:  {alert.details.get('current_median', 'N/A')}")
        
        # Log warnings
        for alert in warning_alerts:
            logger.warning("")
            logger.warning(f"⚠️  {alert.message}")
            logger.warning(f"   Metric:       {alert.metric.upper()}")
            if alert.change_pct != 0:
                logger.warning(f"   Baseline:     {alert.baseline_value:.3f}")
                logger.warning(f"   Current:      {alert.current_value:.3f}")
                logger.warning(f"   Change:       {alert.change_pct:+.1f}%")
            else:
                logger.warning(f"   Affected:     {alert.affected_campaigns} campaigns")
        
        # Log info alerts
        for alert in info_alerts:
            logger.info(f"ℹ️  {alert.message}")
        
        logger.warning("")
        logger.warning("=" * 70)
        
        # Suggest action if critical alerts
        if critical_alerts:
            logger.warning("💡 Recommendations:")
            logger.warning("   1. Verify data quality and completeness")
            logger.warning("   2. Check for external factors (seasonality, holidays)")
            logger.warning("   3. Consider updating baseline if drift is expected")
            logger.warning("   4. Review campaign changes in affected period")
            logger.warning("=" * 70)
