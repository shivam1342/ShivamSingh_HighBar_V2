"""
HealthChecker: Pre-flight validation for data quality and system health.

Runs comprehensive checks before pipeline execution to catch issues early.
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.monitoring.alert_manager import AlertManager, AlertSeverity

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result from a single health check."""
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    severity: AlertSeverity = AlertSeverity.INFO


class HealthChecker:
    """
    Performs comprehensive health checks on data and system state.
    
    Checks include:
    - Data freshness (age of most recent data)
    - Data completeness (missing values, row counts)
    - Data validity (value ranges, negative values)
    - Schema consistency (columns, types)
    """
    
    def __init__(self, config: Dict[str, Any], alert_manager: AlertManager):
        """
        Initialize HealthChecker.
        
        Args:
            config: Application configuration
            alert_manager: AlertManager instance for raising alerts
        """
        self.config = config
        self.alert_manager = alert_manager
        
        health_config = config.get('monitoring', {}).get('health_checks', {})
        self.enabled = health_config.get('enabled', True)
        self.max_data_age_hours = health_config.get('max_data_age_hours', 24)
        self.max_missing_pct = health_config.get('max_missing_pct', 5.0)
        self.check_schema_drift = health_config.get('check_schema_drift', True)
        
        self.results: List[HealthCheckResult] = []
    
    def run_all_checks(self, df: pd.DataFrame, data_summary: Dict[str, Any]) -> bool:
        """
        Run all health checks.
        
        Args:
            df: DataFrame to validate
            data_summary: Summary from DataLoader
        
        Returns:
            True if all critical checks pass, False otherwise
        """
        if not self.enabled:
            logger.info("Health checks disabled")
            return True
        
        logger.info("🏥 Running pre-flight health checks...")
        
        self.results = []
        
        # Run checks
        self._check_data_freshness(data_summary)
        self._check_data_completeness(df)
        self._check_data_validity(df)
        self._check_schema_consistency(df)
        self._check_metric_ranges(df)
        
        # Log results
        self._log_health_report()
        
        # Determine overall health
        critical_failures = [r for r in self.results if not r.passed and r.severity == AlertSeverity.CRITICAL]
        
        if critical_failures:
            logger.error(f"❌ Health check FAILED: {len(critical_failures)} critical issue(s)")
            return False
        
        warnings = [r for r in self.results if not r.passed and r.severity == AlertSeverity.WARNING]
        if warnings:
            logger.warning(f"⚠️  Health check passed with {len(warnings)} warning(s)")
        else:
            logger.info("✅ All health checks passed")
        
        return True
    
    def _check_data_freshness(self, data_summary: Dict[str, Any]) -> None:
        """Check age of most recent data."""
        try:
            date_range = data_summary.get('date_range', {})
            end_date_str = date_range.get('end')
            
            if not end_date_str:
                self.results.append(HealthCheckResult(
                    check_name="data_freshness",
                    passed=False,
                    message="Cannot determine data age (no end_date)",
                    severity=AlertSeverity.WARNING
                ))
                return
            
            # Parse end date
            end_date = pd.to_datetime(end_date_str)
            now = pd.Timestamp.now()
            age_hours = (now - end_date).total_seconds() / 3600
            
            if age_hours > self.max_data_age_hours:
                # Stale data
                self.results.append(HealthCheckResult(
                    check_name="data_freshness",
                    passed=False,
                    message=f"Data is {age_hours:.1f} hours old (threshold: {self.max_data_age_hours}h)",
                    details={"age_hours": age_hours, "last_update": end_date_str},
                    severity=AlertSeverity.WARNING
                ))
                
                self.alert_manager.add_data_freshness_alert(
                    age_hours=age_hours,
                    threshold_hours=self.max_data_age_hours
                )
            else:
                self.results.append(HealthCheckResult(
                    check_name="data_freshness",
                    passed=True,
                    message=f"Data is fresh ({age_hours:.1f} hours old)",
                    details={"age_hours": age_hours}
                ))
        
        except Exception as e:
            logger.error(f"Data freshness check failed: {e}")
            self.results.append(HealthCheckResult(
                check_name="data_freshness",
                passed=False,
                message=f"Check error: {str(e)}",
                severity=AlertSeverity.WARNING
            ))
    
    def _check_data_completeness(self, df: pd.DataFrame) -> None:
        """Check for missing values and row counts."""
        # Check row count
        if len(df) == 0:
            self.results.append(HealthCheckResult(
                check_name="data_completeness",
                passed=False,
                message="No data rows found",
                severity=AlertSeverity.CRITICAL
            ))
            
            self.alert_manager.add_missing_data_alert(
                days_missing=999,
                last_data_date="unknown"
            )
            return
        
        # Check missing values
        missing_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
        
        if missing_pct > self.max_missing_pct:
            self.results.append(HealthCheckResult(
                check_name="data_completeness",
                passed=False,
                message=f"High missing values: {missing_pct:.1f}% (threshold: {self.max_missing_pct}%)",
                details={"missing_pct": missing_pct, "total_rows": len(df)},
                severity=AlertSeverity.WARNING
            ))
        else:
            self.results.append(HealthCheckResult(
                check_name="data_completeness",
                passed=True,
                message=f"Data complete: {len(df)} rows, {missing_pct:.2f}% missing",
                details={"total_rows": len(df), "missing_pct": missing_pct}
            ))
    
    def _check_data_validity(self, df: pd.DataFrame) -> None:
        """Check for invalid values (negatives, nulls in required fields)."""
        issues = []
        
        # Check for negative spend
        if 'spend' in df.columns:
            negative_spend = (df['spend'] < 0).sum()
            if negative_spend > 0:
                issues.append(f"{negative_spend} negative spend values")
        
        # Check for negative ROAS
        if 'roas' in df.columns:
            negative_roas = (df['roas'] < 0).sum()
            if negative_roas > 0:
                issues.append(f"{negative_roas} negative ROAS values")
        
        # Check for zero impressions with spend
        if 'impressions' in df.columns and 'spend' in df.columns:
            zero_impressions_with_spend = ((df['impressions'] == 0) & (df['spend'] > 0)).sum()
            if zero_impressions_with_spend > 0:
                issues.append(f"{zero_impressions_with_spend} campaigns with spend but zero impressions")
        
        if issues:
            self.results.append(HealthCheckResult(
                check_name="data_validity",
                passed=False,
                message="Data validity issues found",
                details={"issues": issues},
                severity=AlertSeverity.WARNING
            ))
        else:
            self.results.append(HealthCheckResult(
                check_name="data_validity",
                passed=True,
                message="All data values valid"
            ))
    
    def _check_schema_consistency(self, df: pd.DataFrame) -> None:
        """Check required columns and data types."""
        required_columns = ['date', 'campaign', 'spend', 'impressions', 'clicks']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            self.results.append(HealthCheckResult(
                check_name="schema_consistency",
                passed=False,
                message=f"Missing required columns: {missing_columns}",
                details={"missing": missing_columns},
                severity=AlertSeverity.CRITICAL
            ))
        else:
            self.results.append(HealthCheckResult(
                check_name="schema_consistency",
                passed=True,
                message="All required columns present"
            ))
    
    def _check_metric_ranges(self, df: pd.DataFrame) -> None:
        """Check if metrics are within reasonable ranges."""
        issues = []
        
        # Check ROAS range
        if 'roas' in df.columns:
            max_roas = df['roas'].max()
            if max_roas > 1000:  # Suspiciously high
                issues.append(f"ROAS max {max_roas:.1f} (>1000 - possible error?)")
        
        # Check CTR range
        if 'ctr' in df.columns:
            max_ctr = df['ctr'].max()
            if max_ctr > 0.5:  # >50% CTR is suspicious
                issues.append(f"CTR max {max_ctr:.2%} (>50% - possible error?)")
        
        # Check spend range
        if 'spend' in df.columns:
            max_spend = df['spend'].max()
            if max_spend > 100000:  # >$100k per row
                issues.append(f"Spend max ${max_spend:,.0f} (>$100k - verify if expected)")
        
        if issues:
            self.results.append(HealthCheckResult(
                check_name="metric_ranges",
                passed=True,  # Warning, not failure
                message="Unusual metric values detected",
                details={"warnings": issues},
                severity=AlertSeverity.INFO
            ))
        else:
            self.results.append(HealthCheckResult(
                check_name="metric_ranges",
                passed=True,
                message="All metrics within expected ranges"
            ))
    
    def _log_health_report(self) -> None:
        """Log formatted health check report."""
        logger.info("━" * 70)
        logger.info("🏥 HEALTH CHECK REPORT")
        logger.info("━" * 70)
        
        for result in self.results:
            if result.passed:
                logger.info(f"✅ {result.check_name}: {result.message}")
            else:
                if result.severity == AlertSeverity.CRITICAL:
                    logger.error(f"❌ {result.check_name}: {result.message}")
                else:
                    logger.warning(f"⚠️  {result.check_name}: {result.message}")
            
            if result.details:
                for key, value in result.details.items():
                    if isinstance(value, list):
                        logger.info(f"     {key}: {', '.join(str(v) for v in value)}")
                    else:
                        logger.info(f"     {key}: {value}")
        
        logger.info("━" * 70)
        
        # Overall status
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        failed = total - passed
        
        if failed == 0:
            logger.info(f"Overall Health: EXCELLENT ✅ ({passed}/{total} passed)")
        elif any(r.severity == AlertSeverity.CRITICAL and not r.passed for r in self.results):
            logger.error(f"Overall Health: CRITICAL ❌ ({passed}/{total} passed)")
        else:
            logger.warning(f"Overall Health: GOOD ⚠️  ({passed}/{total} passed, {failed} warnings)")
        
        logger.info("━" * 70)
    
    def get_failed_checks(self) -> List[HealthCheckResult]:
        """Get all failed checks."""
        return [r for r in self.results if not r.passed]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get health check summary."""
        return {
            'total_checks': len(self.results),
            'passed': sum(1 for r in self.results if r.passed),
            'failed': sum(1 for r in self.results if not r.passed),
            'critical_failures': sum(1 for r in self.results 
                                    if not r.passed and r.severity == AlertSeverity.CRITICAL),
            'warnings': sum(1 for r in self.results 
                          if not r.passed and r.severity == AlertSeverity.WARNING),
            'all_passed': all(r.passed for r in self.results)
        }
