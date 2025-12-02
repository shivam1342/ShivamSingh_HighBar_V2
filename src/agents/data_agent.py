"""
Data Agent - Loads dataset and executes analytical queries
"""
import pandas as pd
import numpy as np
import logging
import time
from typing import Dict, Any, List
from src.utils.data_loader import DataLoader
from src.utils.structured_logger import StructuredLogger
from src.utils.threshold_manager import ThresholdManager

logger = logging.getLogger(__name__)


class DataAgent:
    """
    Executes data queries and returns analytical results
    """
    
    # Metric aliases mapping
    METRIC_ALIASES = {
        'sales': 'revenue',
        'conversions': 'purchases',
        'cost': 'spend'
    }
    
    # Valid base metrics available in dataset
    VALID_BASE_METRICS = {'spend', 'impressions', 'clicks', 'purchases', 'revenue'}
    
    # Valid calculated metrics
    VALID_CALCULATED_METRICS = {'ctr', 'roas', 'cpc', 'cpm', 'cvr'}
    
    def __init__(self, data_loader: DataLoader, config: Dict[str, Any] = None, structured_logger: StructuredLogger = None):
        self.loader = data_loader
        self.df = None
        self.config = config or {}
        self.logger = structured_logger or StructuredLogger()
        
        # Initialize threshold manager for default threshold resolution
        self.threshold_mgr = ThresholdManager(self.config)
        
    def initialize(self):
        """Load the dataset"""
        self.df = self.loader.load()
        logger.info("Data Agent initialized")
        
    def _normalize_metric(self, metric: str) -> str:
        """
        Validate and normalize metric names, mapping aliases to actual column names
        
        Args:
            metric: Raw metric name from planner
            
        Returns:
            Normalized metric name
            
        Raises:
            DataValidationError: If metric is invalid and has no mapping
        """
        metric_lower = metric.lower().strip()
        
        # Check if it's an alias
        if metric_lower in self.METRIC_ALIASES:
            normalized = self.METRIC_ALIASES[metric_lower]
            logger.info(f"Mapped metric alias '{metric}' → '{normalized}'")
            return normalized
        
        # Check if it's a valid base or calculated metric
        if metric_lower in self.VALID_BASE_METRICS or metric_lower in self.VALID_CALCULATED_METRICS:
            return metric_lower
        
        # Invalid metric - provide helpful error
        from src.utils.exceptions import DataValidationError
        available = sorted(self.VALID_BASE_METRICS | self.VALID_CALCULATED_METRICS | set(self.METRIC_ALIASES.keys()))
        raise DataValidationError(
            f"Invalid metric '{metric}'. Available metrics: {available}",
            field_name="metric",
            field_value=metric,
            expected_values=available
        )
    
    def execute_subtask(self, subtask: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single subtask from the planner
        
        Args:
            subtask: Task definition from planner
            
        Returns:
            Analysis results
        """
        task_type = subtask.get("task_type")
        params = subtask.get("parameters", {})
        
        # Log subtask start
        self.logger.log_agent_start(
            "data_agent",
            input_data={
                "task_type": task_type,
                "parameters": params
            }
        )
        
        start_time = time.time()
        
        try:
            logger.info(f"Executing subtask: {task_type}")
            
            if task_type == "analyze_metric_trend":
                result = self._analyze_trend(params)
            elif task_type == "identify_underperformers":
                result = self._identify_underperformers(params)
            elif task_type == "segment_analysis":
                result = self._segment_analysis(params)
            elif task_type == "creative_analysis":
                result = self._creative_analysis(params)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                result = {"error": f"Unknown task type: {task_type}"}
            
            # Log completion
            duration = time.time() - start_time
            self.logger.log_agent_complete(
                "data_agent",
                output_data={
                    "task_type": task_type,
                    "result_keys": list(result.keys()),
                    "data_points": len(result.get("daily_values", [])) if "daily_values" in result else 0
                },
                duration_seconds=duration
            )
            
            return result
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            self.logger.log_agent_error(
                "data_agent",
                error=e,
                context={
                    "task_type": task_type,
                    "parameters": params,
                    "duration_before_error": duration
                }
            )
            raise
    
    def _analyze_trend(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze metric trend over time"""
        raw_metric = params.get("metric", "roas")
        timeframe = params.get("timeframe", "last_7_days")
        
        # Normalize metric
        try:
            metric = self._normalize_metric(raw_metric)
        except Exception as e:
            logger.warning(f"Invalid metric '{raw_metric}', using 'roas': {e}")
            metric = "roas"
        
        # Extract number of days
        days = int(timeframe.split("_")[1]) if "last_" in timeframe else 7
        
        # Get daily aggregated data
        daily = self.df.groupby('date').agg({
            'spend': 'sum',
            'revenue': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'purchases': 'sum'
        }).reset_index()
        
        daily['roas'] = daily['revenue'] / daily['spend'].replace(0, np.nan)
        daily['ctr'] = daily['clicks'] / daily['impressions'].replace(0, np.nan)
        
        # Get recent period
        recent_data = daily.tail(days)
        previous_data = daily.head(len(daily) - days).tail(days)
        
        recent_avg = recent_data[metric].mean()
        previous_avg = previous_data[metric].mean()
        change_pct = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg != 0 else 0
        
        return {
            "metric": metric,
            "timeframe": timeframe,
            "recent_avg": float(recent_avg),
            "previous_avg": float(previous_avg),
            "change_pct": float(change_pct),
            "trend": "increasing" if change_pct > 0 else "decreasing",
            "daily_values": recent_data[[metric]].tail(7).to_dict('records')
        }
    
    def _identify_underperformers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find low-performing campaigns/adsets"""
        raw_metric = params.get("metric", "ctr")
        
        # Parse threshold parameter (handle various formats)
        threshold_param = params.get("threshold")
        
        # If no threshold provided, use ThresholdManager
        if threshold_param is None:
            threshold = self.threshold_mgr.get_threshold(
                metric=raw_metric,
                use_adaptive=False
            )
            logger.debug(f"No threshold provided, using ThresholdManager default: {threshold}")
        else:
            try:
                # Handle string thresholds like "top_10", "zero", etc.
                if isinstance(threshold_param, str):
                    if "zero" in threshold_param.lower():
                        threshold = 0.0
                    elif "top" in threshold_param.lower():
                        # For "top_N" queries, use ThresholdManager default
                        threshold = self.threshold_mgr.get_threshold(
                            metric=raw_metric,
                            use_adaptive=False
                        )
                    else:
                        threshold = float(threshold_param)
                else:
                    threshold = float(threshold_param)
            except (ValueError, TypeError):
                # Fallback to ThresholdManager instead of hardcoded value
                logger.warning(f"Invalid threshold value '{threshold_param}', using ThresholdManager default")
                threshold = self.threshold_mgr.get_threshold(
                    metric=raw_metric,
                    use_adaptive=False
                )
        
        # Normalize and validate metric
        try:
            metric = self._normalize_metric(raw_metric)
        except Exception as e:
            logger.error(f"Metric validation failed: {e}")
            # Fallback to CTR if metric is invalid
            logger.warning(f"Using fallback metric 'ctr' instead of invalid '{raw_metric}'")
            metric = "ctr"
        
        # Group by campaign and adset
        grouped = self.df.groupby(['campaign_name', 'adset_name']).agg({
            'spend': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'purchases': 'sum',
            'revenue': 'sum'
        }).reset_index()
        
        # Calculate metrics
        grouped['ctr'] = grouped['clicks'] / grouped['impressions'].replace(0, np.nan)
        grouped['roas'] = grouped['revenue'] / grouped['spend'].replace(0, np.nan)
        grouped['cvr'] = grouped['purchases'] / grouped['clicks'].replace(0, np.nan)
        grouped['cpc'] = grouped['spend'] / grouped['clicks'].replace(0, np.nan)
        grouped['cpm'] = (grouped['spend'] / grouped['impressions'].replace(0, np.nan)) * 1000
        
        # Filter underperformers (handle both zero and low values)
        if metric in ['revenue', 'purchases']:  # For "zero sales/revenue" queries
            underperformers = grouped[grouped[metric] <= threshold].sort_values('spend', ascending=False)
        else:
            underperformers = grouped[grouped[metric] < threshold].sort_values(metric)
        
        return {
            "metric": metric,
            "threshold": threshold,
            "count": len(underperformers),
            "top_underperformers": underperformers.head(10).to_dict('records')
        }
    
    def _segment_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare performance across segments"""
        dimension = params.get("dimension", "creative_type")
        raw_metric = params.get("metric", "roas")
        
        # Normalize metric
        try:
            metric = self._normalize_metric(raw_metric)
        except Exception as e:
            logger.warning(f"Invalid metric '{raw_metric}', using 'roas': {e}")
            metric = "roas"
        
        # Group by dimension
        grouped = self.df.groupby(dimension).agg({
            'spend': 'sum',
            'revenue': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'purchases': 'sum'
        }).reset_index()
        
        grouped['roas'] = grouped['revenue'] / grouped['spend'].replace(0, np.nan)
        grouped['ctr'] = grouped['clicks'] / grouped['impressions'].replace(0, np.nan)
        
        return {
            "dimension": dimension,
            "metric": metric,
            "segments": grouped.sort_values(metric, ascending=False).to_dict('records')
        }
    
    def _creative_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze creative performance"""
        # Get creative performance by type and message
        creative_perf = self.df.groupby(['creative_type', 'creative_message']).agg({
            'spend': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'ctr': 'mean',
            'purchases': 'sum',
            'revenue': 'sum',
            'roas': 'mean'
        }).reset_index()
        
        # Sort by CTR
        top_performers = creative_perf.nlargest(10, 'ctr')
        bottom_performers = creative_perf.nsmallest(10, 'ctr')
        
        return {
            "total_creative_variants": len(creative_perf),
            "top_performers": top_performers.to_dict('records'),
            "bottom_performers": bottom_performers.to_dict('records'),
            "creative_type_summary": self.df.groupby('creative_type')['ctr'].mean().to_dict()
        }
    
    def get_context_for_insights(self) -> Dict[str, Any]:
        """Prepare dataset context for insight generation"""
        # Get unique dimensions for context
        dimensions = {
            "creative_types": self.df['creative_type'].value_counts().to_dict(),
            "platforms": self.df['platform'].value_counts().to_dict(),
            "audience_types": self.df['audience_type'].value_counts().to_dict(),
            "countries": self.df['country'].value_counts().to_dict()
        }
        
        return {
            "summary": self.loader.get_summary(),
            "time_series": self.loader.get_time_series_summary('roas', window=7),
            "dimensions": dimensions
        }
