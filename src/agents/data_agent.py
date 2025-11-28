"""
Data Agent - Loads dataset and executes analytical queries
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List
from src.utils.data_loader import DataLoader

logger = logging.getLogger(__name__)


class DataAgent:
    """
    Executes data queries and returns analytical results
    """
    
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.df = None
        
    def initialize(self):
        """Load the dataset"""
        self.df = self.loader.load()
        logger.info("Data Agent initialized")
        
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
        
        logger.info(f"Executing subtask: {task_type}")
        
        if task_type == "analyze_metric_trend":
            return self._analyze_trend(params)
        elif task_type == "identify_underperformers":
            return self._identify_underperformers(params)
        elif task_type == "segment_analysis":
            return self._segment_analysis(params)
        elif task_type == "creative_analysis":
            return self._creative_analysis(params)
        else:
            logger.warning(f"Unknown task type: {task_type}")
            return {"error": f"Unknown task type: {task_type}"}
    
    def _analyze_trend(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze metric trends over time"""
        metric = params.get("metric", "roas")
        timeframe = params.get("timeframe", "last_7_days")
        
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
        metric = params.get("metric", "ctr")
        threshold = params.get("threshold", 0.01)
        
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
        
        # Filter underperformers
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
        metric = params.get("metric", "roas")
        
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
