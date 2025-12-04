"""
AlertManager: Centralized alert collection and formatting.

Handles alerts from all agents with severity levels, formatting,
and alert history tracking.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "CRITICAL"  # Cannot produce reliable results
    WARNING = "WARNING"    # Degraded results expected
    INFO = "INFO"          # Informational only


@dataclass
class Alert:
    """
    Represents a single alert from any agent.
    
    Attributes:
        severity: Alert severity level
        source: Agent/component that raised the alert
        message: Human-readable alert message
        details: Additional context (metrics, thresholds, etc.)
        recommendation: Suggested action to resolve
        timestamp: When alert was created
        alert_id: Unique identifier for deduplication
    """
    severity: AlertSeverity
    source: str
    message: str
    details: Optional[Dict[str, Any]] = None
    recommendation: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    alert_id: Optional[str] = None
    
    def format(self) -> str:
        """Format alert for console display."""
        # Severity emoji
        emoji_map = {
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.WARNING: "⚠️ ",
            AlertSeverity.INFO: "ℹ️ "
        }
        emoji = emoji_map[self.severity]
        
        lines = [
            f"{emoji} {self.severity.value}: {self.message}",
            f"   Source: {self.source}"
        ]
        
        # Add details
        if self.details:
            for key, value in self.details.items():
                lines.append(f"   {key}: {value}")
        
        # Add recommendation
        if self.recommendation:
            lines.append(f"   💡 Recommendation: {self.recommendation}")
        
        return "\n".join(lines)


class AlertManager:
    """
    Centralized alert management system.
    
    Collects alerts from all agents, deduplicates, formats,
    and provides summary reports.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AlertManager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        alert_config = config.get('monitoring', {}).get('alerts', {})
        
        self.enabled = alert_config.get('enabled', True)
        self.confidence_threshold = alert_config.get('confidence_threshold', 0.5)
        self.quality_threshold = alert_config.get('quality_threshold', 0.6)
        self.min_data_days = alert_config.get('min_data_days', 7)
        self.max_history = alert_config.get('alert_history_size', 100)
        
        # Alert storage
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self.alert_counts = defaultdict(int)  # Count by alert_id
        
        logger.debug(f"AlertManager initialized (enabled={self.enabled})")
    
    def add_alert(
        self,
        severity: AlertSeverity,
        source: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recommendation: Optional[str] = None,
        alert_id: Optional[str] = None
    ) -> Alert:
        """
        Add new alert to the system.
        
        Args:
            severity: Alert severity level
            source: Agent/component raising alert
            message: Human-readable message
            details: Additional context
            recommendation: Suggested action
            alert_id: ID for deduplication (optional)
        
        Returns:
            Created Alert object
        """
        if not self.enabled:
            return None
        
        alert = Alert(
            severity=severity,
            source=source,
            message=message,
            details=details,
            recommendation=recommendation,
            alert_id=alert_id
        )
        
        self.alerts.append(alert)
        
        # Track alert history
        if alert_id:
            self.alert_counts[alert_id] += 1
        
        # Maintain history size
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)
        
        return alert
    
    def add_low_confidence_alert(
        self,
        insight_id: str,
        confidence: float,
        threshold: float,
        reason: str
    ) -> Alert:
        """
        Add alert for low-confidence insight.
        
        Args:
            insight_id: Insight identifier
            confidence: Actual confidence score
            threshold: Minimum acceptable confidence
            reason: Why confidence is low
        
        Returns:
            Created Alert object
        """
        return self.add_alert(
            severity=AlertSeverity.WARNING,
            source="insight_agent",
            message=f"Insight '{insight_id}' has low confidence ({confidence:.2f} < {threshold:.2f})",
            details={
                "confidence": f"{confidence:.2f}",
                "threshold": f"{threshold:.2f}",
                "reason": reason
            },
            recommendation="Review evidence or gather more data before using this insight",
            alert_id=f"low_confidence_{insight_id}"
        )
    
    def add_quality_alert(
        self,
        quality_score: float,
        threshold: float,
        rejected_count: int,
        total_count: int
    ) -> Alert:
        """
        Add alert for low quality score.
        
        Args:
            quality_score: Actual quality score
            threshold: Minimum acceptable quality
            rejected_count: Number of rejected insights
            total_count: Total insights evaluated
        
        Returns:
            Created Alert object
        """
        severity = AlertSeverity.CRITICAL if quality_score < 0.5 else AlertSeverity.WARNING
        
        return self.add_alert(
            severity=severity,
            source="evaluator",
            message=f"Quality score {quality_score:.2f} below threshold {threshold:.2f}",
            details={
                "quality_score": f"{quality_score:.2f}",
                "threshold": f"{threshold:.2f}",
                "rejected": f"{rejected_count}/{total_count}",
                "pass_rate": f"{((total_count - rejected_count) / total_count * 100):.1f}%"
            },
            recommendation="Review rejected insights or adjust quality thresholds",
            alert_id="quality_below_threshold"
        )
    
    def add_missing_data_alert(
        self,
        days_missing: int,
        last_data_date: str
    ) -> Alert:
        """
        Add alert for missing recent data.
        
        Args:
            days_missing: Number of days without data
            last_data_date: Date of most recent data
        
        Returns:
            Created Alert object
        """
        return self.add_alert(
            severity=AlertSeverity.CRITICAL,
            source="health_checker",
            message=f"No data in last {days_missing} days",
            details={
                "days_missing": days_missing,
                "last_data_date": last_data_date,
                "threshold": f"{self.min_data_days} days"
            },
            recommendation="Check data pipeline and ensure data is being loaded",
            alert_id="missing_data"
        )
    
    def add_data_freshness_alert(
        self,
        age_hours: float,
        threshold_hours: int
    ) -> Alert:
        """
        Add alert for stale data.
        
        Args:
            age_hours: Age of data in hours
            threshold_hours: Maximum acceptable age
        
        Returns:
            Created Alert object
        """
        return self.add_alert(
            severity=AlertSeverity.WARNING,
            source="health_checker",
            message=f"Data is {age_hours:.1f} hours old (threshold: {threshold_hours}h)",
            details={
                "age_hours": f"{age_hours:.1f}",
                "threshold_hours": threshold_hours
            },
            recommendation="Consider refreshing data or adjusting threshold",
            alert_id="data_freshness"
        )
    
    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        source: Optional[str] = None
    ) -> List[Alert]:
        """
        Get alerts, optionally filtered.
        
        Args:
            severity: Filter by severity level
            source: Filter by source agent
        
        Returns:
            List of matching alerts
        """
        filtered = self.alerts
        
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        
        if source:
            filtered = [a for a in filtered if a.source == source]
        
        return filtered
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get alert summary statistics.
        
        Returns:
            Dictionary with alert counts and details
        """
        return {
            'total_alerts': len(self.alerts),
            'critical_count': len(self.get_alerts(AlertSeverity.CRITICAL)),
            'warning_count': len(self.get_alerts(AlertSeverity.WARNING)),
            'info_count': len(self.get_alerts(AlertSeverity.INFO)),
            'sources': list(set(a.source for a in self.alerts)),
            'has_critical': any(a.severity == AlertSeverity.CRITICAL for a in self.alerts)
        }
    
    def log_all_alerts(self) -> None:
        """Log all alerts to console with formatting."""
        if not self.alerts:
            logger.info("✅ No alerts - all systems nominal")
            return
        
        summary = self.get_summary()
        
        logger.warning("=" * 70)
        logger.warning(f"📬 ALERT SUMMARY: {summary['total_alerts']} alert(s)")
        logger.warning("=" * 70)
        
        # Log critical alerts first
        critical = self.get_alerts(AlertSeverity.CRITICAL)
        if critical:
            logger.critical("")
            logger.critical(f"🚨 CRITICAL ALERTS: {len(critical)}")
            for alert in critical:
                for line in alert.format().split('\n'):
                    logger.critical(line)
                logger.critical("")
        
        # Then warnings
        warnings = self.get_alerts(AlertSeverity.WARNING)
        if warnings:
            logger.warning("")
            logger.warning(f"⚠️  WARNING ALERTS: {len(warnings)}")
            for alert in warnings:
                for line in alert.format().split('\n'):
                    logger.warning(line)
                logger.warning("")
        
        # Finally info
        info = self.get_alerts(AlertSeverity.INFO)
        if info:
            logger.info("")
            logger.info(f"ℹ️  INFO ALERTS: {len(info)}")
            for alert in info:
                logger.info(alert.format())
                logger.info("")
        
        logger.warning("=" * 70)
        
        # Add recommendations summary
        if critical:
            logger.warning("💡 RECOMMENDED ACTIONS:")
            for i, alert in enumerate(critical, 1):
                if alert.recommendation:
                    logger.warning(f"   {i}. {alert.recommendation} ({alert.source})")
            logger.warning("=" * 70)
    
    def clear_alerts(self) -> None:
        """Clear current alerts (keep history)."""
        self.alerts = []
    
    def get_recurring_alerts(self, min_count: int = 3) -> List[tuple]:
        """
        Get alerts that have occurred multiple times.
        
        Args:
            min_count: Minimum occurrences to be considered recurring
        
        Returns:
            List of (alert_id, count) tuples
        """
        return [(alert_id, count) for alert_id, count in self.alert_counts.items() 
                if count >= min_count]
