"""
Centralized Threshold Management System

Provides intelligent threshold resolution with configurable priority:
1. Campaign-specific overrides (highest priority)
2. Metric-specific defaults
3. Adaptive adjustments based on data quality
4. Global defaults (lowest priority)

Supports historical data-driven threshold calculation and caching for performance.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ThresholdManager:
    """
    Centralized threshold management with priority resolution and historical learning.
    
    Priority Resolution Order (highest to lowest):
    1. Campaign-specific overrides: thresholds.campaigns.{campaign_id}.{metric}
    2. Metric-specific defaults: thresholds.metrics.{metric}.default
    3. Adaptive adjustments: Apply multipliers based on data quality
    4. Global defaults: thresholds.{metric}_default
    
    Features:
    - Per-campaign and per-metric threshold overrides
    - Historical data-driven threshold calculation
    - Adaptive multipliers based on data quality (volatile/stable)
    - Caching for performance optimization
    - Full observability with detailed logging
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ThresholdManager with configuration.
        
        Args:
            config: Full configuration dictionary containing thresholds section
        """
        self.config = config
        self.thresholds_config = config.get("thresholds", {})
        
        # Cache for resolved thresholds (key: metric|campaign|quality -> value)
        self._cache: Dict[str, float] = {}
        
        # Cache for historical thresholds (key: metric -> {value, timestamp})
        self._historical_cache: Dict[str, Dict[str, Any]] = {}
        
        # Load configuration sections
        self.global_defaults = self._load_global_defaults()
        self.metric_defaults = self.thresholds_config.get("metrics", {})
        self.campaign_overrides = self.thresholds_config.get("campaigns", {})
        self.historical_config = self.thresholds_config.get("historical", {})
        self.adaptive_config = self._load_adaptive_config()
        
        logger.info("ThresholdManager initialized with campaign overrides, metric defaults, and adaptive rules")
        logger.debug(f"Loaded {len(self.campaign_overrides or {})} campaign overrides, {len(self.metric_defaults or {})} metric defaults")
    
    def _load_global_defaults(self) -> Dict[str, float]:
        """Load global default thresholds from config."""
        planner_config = self.thresholds_config.get("planner", {})
        return {
            "ctr": planner_config.get("default_underperformer_threshold", 0.01),
            "cvr": planner_config.get("default_underperformer_threshold", 0.01),
            "roas": planner_config.get("default_roas_threshold", 1.0),
            "confidence": self.thresholds_config.get("confidence_min", 0.6),
            "quality": self.thresholds_config.get("quality_score_min", 0.7),
            "roas_change": self.thresholds_config.get("roas_change_threshold", 0.15),
            "min_spend": self.thresholds_config.get("min_spend_for_analysis", 100)
        }
    
    def _load_adaptive_config(self) -> Dict[str, Any]:
        """Load adaptive multiplier configuration."""
        planner_adaptive = self.thresholds_config.get("planner", {}).get("adaptive", {})
        evaluator_adaptive = self.thresholds_config.get("evaluator", {}).get("adaptive", {})
        
        return {
            "planner": {
                "high_variance_multiplier": planner_adaptive.get("high_variance_multiplier", 0.7),
                "low_variance_multiplier": planner_adaptive.get("low_variance_multiplier", 1.2),
                "high_variance_cv": planner_adaptive.get("high_variance_cv", 0.5),
                "low_variance_cv": planner_adaptive.get("low_variance_cv", 0.2)
            },
            "evaluator": {
                "volatile_confidence_multiplier": evaluator_adaptive.get("volatile_confidence_multiplier", 0.7),
                "stable_confidence_multiplier": evaluator_adaptive.get("stable_confidence_multiplier", 1.2),
                "volatile_quality_multiplier": evaluator_adaptive.get("volatile_quality_multiplier", 0.85),
                "stable_quality_multiplier": evaluator_adaptive.get("stable_quality_multiplier", 1.1)
            }
        }
    
    def get_threshold(
        self,
        metric: str,
        campaign_id: Optional[str] = None,
        data_quality: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        use_adaptive: bool = True
    ) -> float:
        """
        Get threshold with intelligent priority resolution.
        
        Priority (highest to lowest):
        1. Campaign-specific override
        2. Metric-specific default
        3. Adaptive adjustment (if data_quality provided and use_adaptive=True)
        4. Global default
        
        Args:
            metric: Metric name (ctr, roas, cvr, confidence, quality, etc.)
            campaign_id: Optional campaign ID for campaign-specific overrides
            data_quality: Optional data quality level (volatile, stable, medium)
            context: Optional additional context for threshold resolution
            use_adaptive: Whether to apply adaptive multipliers (default: True)
        
        Returns:
            Resolved threshold value
        """
        # Build cache key
        cache_key = f"{metric}|{campaign_id or 'none'}|{data_quality or 'none'}"
        
        # Check cache
        if cache_key in self._cache:
            logger.debug(f"Cache hit: {cache_key} → {self._cache[cache_key]}")
            return self._cache[cache_key]
        
        logger.info(f"Resolving threshold for metric='{metric}', campaign='{campaign_id}', quality='{data_quality}'")
        
        # Priority 1: Campaign-specific override
        base_threshold = self._get_campaign_override(metric, campaign_id)
        source = "campaign override"
        
        # Priority 2: Metric-specific default
        if base_threshold is None:
            base_threshold = self._get_metric_default(metric)
            source = "metric default"
        
        # Priority 3: Global default
        if base_threshold is None:
            base_threshold = self.global_defaults.get(metric)
            source = "global default"
        
        # Fallback if metric not found
        if base_threshold is None:
            logger.warning(f"No threshold found for metric '{metric}', using 0.01 as fallback")
            base_threshold = 0.01
            source = "fallback"
        
        logger.info(f"Base threshold from {source}: {base_threshold}")
        
        # Priority 4: Apply adaptive multiplier if requested
        final_threshold = base_threshold
        if use_adaptive and data_quality:
            multiplier = self._get_adaptive_multiplier(metric, data_quality)
            if multiplier != 1.0:
                final_threshold = base_threshold * multiplier
                logger.info(f"Applied adaptive multiplier {multiplier} ({data_quality}): {base_threshold} → {final_threshold:.6f}")
        
        # Cache result
        self._cache[cache_key] = final_threshold
        
        logger.info(f"Final threshold: {final_threshold:.6f} (source: {source}{' + adaptive' if use_adaptive and data_quality else ''})")
        
        return final_threshold
    
    def _get_campaign_override(self, metric: str, campaign_id: Optional[str]) -> Optional[float]:
        """Get campaign-specific threshold override if available."""
        if not campaign_id or not self.campaign_overrides:
            return None
        
        campaign_config = self.campaign_overrides.get(campaign_id, {})
        if metric in campaign_config:
            value = float(campaign_config[metric])
            logger.debug(f"Found campaign override: {campaign_id}.{metric} = {value}")
            return value
        
        return None
    
    def _get_metric_default(self, metric: str) -> Optional[float]:
        """Get metric-specific default threshold."""
        if not self.metric_defaults:
            return None
        
        metric_config = self.metric_defaults.get(metric, {})
        if isinstance(metric_config, dict) and "default" in metric_config:
            value = float(metric_config["default"])
            logger.debug(f"Found metric default: {metric}.default = {value}")
            return value
        elif isinstance(metric_config, (int, float)):
            value = float(metric_config)
            logger.debug(f"Found metric default: {metric} = {value}")
            return value
        
        return None
    
    def _get_adaptive_multiplier(self, metric: str, data_quality: str) -> float:
        """
        Get adaptive multiplier based on data quality.
        
        Args:
            metric: Metric name (determines which adaptive config to use)
            data_quality: Data quality level (volatile, stable, medium)
        
        Returns:
            Multiplier value (1.0 = no change)
        """
        # Determine which adaptive config to use based on metric
        if metric in ["confidence", "quality"]:
            adaptive = self.adaptive_config["evaluator"]
            if data_quality == "volatile":
                key = "volatile_confidence_multiplier" if metric == "confidence" else "volatile_quality_multiplier"
                return adaptive.get(key, 1.0)
            elif data_quality == "stable":
                key = "stable_confidence_multiplier" if metric == "confidence" else "stable_quality_multiplier"
                return adaptive.get(key, 1.0)
        else:
            # For planner metrics (ctr, roas, cvr)
            adaptive = self.adaptive_config["planner"]
            if data_quality == "volatile":
                return adaptive.get("high_variance_multiplier", 1.0)
            elif data_quality == "stable":
                return adaptive.get("low_variance_multiplier", 1.0)
        
        return 1.0  # No adjustment for medium/unknown quality
    
    def calculate_historical_threshold(
        self,
        metric: str,
        historical_data: pd.DataFrame,
        percentile: int = 25,
        min_samples: int = 100,
        cache_duration_hours: int = 24
    ) -> Optional[float]:
        """
        Calculate optimal threshold from historical data distribution.
        
        Uses percentile-based approach to identify underperformers:
        - percentile=25: Bottom 25% of performers are considered underperformers
        - percentile=50: Bottom 50% (median split)
        
        Args:
            metric: Metric name (must exist as column in historical_data)
            historical_data: DataFrame containing historical performance data
            percentile: Percentile to use for threshold (default: 25 = bottom quartile)
            min_samples: Minimum number of samples required (default: 100)
            cache_duration_hours: How long to cache result (default: 24 hours)
        
        Returns:
            Calculated threshold value, or None if insufficient data
        """
        # Check cache first
        if metric in self._historical_cache:
            cached = self._historical_cache[metric]
            cache_age = datetime.now() - cached["timestamp"]
            if cache_age < timedelta(hours=cache_duration_hours):
                logger.debug(f"Using cached historical threshold for {metric}: {cached['value']} (age: {cache_age})")
                return cached["value"]
        
        logger.info(f"Calculating historical threshold for {metric} (percentile={percentile}, min_samples={min_samples})")
        
        # Validate data
        if metric not in historical_data.columns:
            logger.warning(f"Metric '{metric}' not found in historical data columns: {list(historical_data.columns)}")
            return None
        
        # Filter valid values
        valid_data = historical_data[metric].dropna()
        valid_data = valid_data[np.isfinite(valid_data)]
        
        sample_count = len(valid_data)
        if sample_count < min_samples:
            logger.warning(f"Insufficient samples for {metric}: {sample_count} < {min_samples} (min required)")
            return None
        
        logger.info(f"Analyzing {sample_count} samples for {metric}")
        
        # Calculate distribution statistics
        p25 = valid_data.quantile(0.25)
        p50 = valid_data.quantile(0.50)
        p75 = valid_data.quantile(0.75)
        mean = valid_data.mean()
        std = valid_data.std()
        
        logger.info(f"Distribution for {metric}: mean={mean:.4f}, std={std:.4f}")
        logger.info(f"Percentiles: p25={p25:.4f}, p50={p50:.4f}, p75={p75:.4f}")
        
        # Calculate threshold at requested percentile
        threshold = valid_data.quantile(percentile / 100.0)
        
        logger.info(f"Historical threshold (p{percentile}): {threshold:.4f}")
        
        # Cache result
        self._historical_cache[metric] = {
            "value": threshold,
            "timestamp": datetime.now(),
            "sample_count": sample_count,
            "percentile": percentile
        }
        
        logger.info(f"Cached historical threshold for {metric}: {threshold:.4f} (valid for {cache_duration_hours}h)")
        
        return threshold
    
    def get_metric_bounds(self, metric: str) -> Dict[str, Optional[float]]:
        """
        Get performance bounds for a metric (low/default/high thresholds).
        
        Useful for classification:
        - value < low_threshold: Low performer
        - low_threshold <= value < high_threshold: Average performer
        - value >= high_threshold: High performer
        
        Args:
            metric: Metric name
        
        Returns:
            Dictionary with 'low', 'default', 'high' threshold values
        """
        metric_config = self.metric_defaults.get(metric, {})
        
        if isinstance(metric_config, dict):
            return {
                "low": metric_config.get("low_performance_threshold"),
                "default": metric_config.get("default"),
                "high": metric_config.get("high_performance_threshold")
            }
        
        # Fallback to single threshold
        default = self.get_threshold(metric, use_adaptive=False)
        return {
            "low": default * 0.5,  # 50% of default
            "default": default,
            "high": default * 2.0  # 200% of default
        }
    
    def clear_cache(self, metric: Optional[str] = None):
        """
        Clear cached thresholds.
        
        Args:
            metric: If provided, only clear cache for this metric. Otherwise clear all.
        """
        if metric:
            # Clear specific metric from both caches
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{metric}|")]
            for key in keys_to_remove:
                del self._cache[key]
            
            if metric in self._historical_cache:
                del self._historical_cache[metric]
            
            logger.info(f"Cleared cache for metric: {metric} ({len(keys_to_remove)} entries)")
        else:
            # Clear all caches
            self._cache.clear()
            self._historical_cache.clear()
            logger.info("Cleared all threshold caches")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cache usage."""
        return {
            "threshold_cache_size": len(self._cache),
            "historical_cache_size": len(self._historical_cache),
            "cached_metrics": list(self._historical_cache.keys()),
            "cache_entries": list(self._cache.keys())[:10]  # First 10 entries
        }
