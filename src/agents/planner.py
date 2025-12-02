"""
Planner Agent - Decomposes user query into actionable subtasks
"""
import json
import logging
import time
import numpy as np
from typing import Dict, List, Any
from src.utils.llm import LLMClient
from src.utils.structured_logger import StructuredLogger
from src.utils.exceptions import JSONParseError
from src.utils.threshold_manager import ThresholdManager

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Decomposes high-level queries into structured subtasks with adaptive thresholds
    """
    
    def __init__(self, llm_client: LLMClient, config: Dict[str, Any] = None, structured_logger: StructuredLogger = None):
        self.llm = llm_client
        self.logger = structured_logger or StructuredLogger()
        self.config = config or {}
        
        # Initialize centralized threshold manager
        self.threshold_mgr = ThresholdManager(self.config)
        
        # Load adaptive config (for CV thresholds)
        planner_config = self.config.get("thresholds", {}).get("planner", {})
        adaptive_config = planner_config.get("adaptive", {})
        self.high_variance_cv = adaptive_config.get("high_variance_cv", 0.5)
        self.low_variance_cv = adaptive_config.get("low_variance_cv", 0.2)
        
    def plan(self, user_query: str, data_summary: Dict[str, Any], raw_data: Any = None) -> Dict[str, Any]:
        """
        Create execution plan from user query with adaptive thresholds
        
        Args:
            user_query: Natural language query from user
            data_summary: High-level dataset statistics
            raw_data: Optional pandas DataFrame for data quality assessment
            
        Returns:
            Dict with 'plan' (list of subtasks) and 'data_quality' (assessment)
        """
        # Log agent start
        self.logger.log_agent_start(
            "planner",
            input_data={
                "user_query": user_query,
                "data_summary": data_summary
            }
        )
        
        start_time = time.time()
        
        try:
            logger.info(f"Planning for query: {user_query}")
            
            # Assess data quality and adapt thresholds
            data_quality = self._assess_data_quality(raw_data, data_summary)
            adaptive_thresholds = self._adapt_thresholds(data_quality)
            
            logger.info(f"Data quality: {data_quality['quality_level']}, Adaptive thresholds: {adaptive_thresholds}")
            
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_prompt(user_query, data_summary, adaptive_thresholds, data_quality)
            
            # Log LLM call
            llm_start = time.time()
            response = self.llm.generate(user_prompt, system_prompt)
            llm_duration = time.time() - llm_start
            
            self.logger.log_llm_call(
                agent_name="planner",
                prompt=user_prompt,
                system_prompt=system_prompt,
                response=response,
                model=self.llm.model,
                duration_seconds=llm_duration
            )
            
            # Parse JSON response
            try:
                plan = json.loads(response)
                subtasks = plan.get("subtasks", [])
                
                logger.info(f"Generated plan with {len(subtasks)} subtasks")
                
                # Log completion
                duration = time.time() - start_time
                self.logger.log_agent_complete(
                    "planner",
                    output_data={
                        "subtasks": subtasks,
                        "subtask_count": len(subtasks),
                        "data_quality": data_quality,
                        "adaptive_thresholds": adaptive_thresholds
                    },
                    duration_seconds=duration
                )
                
                # Return dict with plan and data_quality (for pipeline compatibility)
                return {
                    'plan': subtasks,
                    'data_quality': data_quality
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse planner response: {e}")
                
                # Log JSON parse error
                self.logger.log_agent_error(
                    "planner",
                    error=JSONParseError(
                        f"Failed to parse JSON from LLM response: {e}",
                        raw_response=response,
                        agent_name="planner"
                    ),
                    context={"raw_response": response[:500]}
                )
                
                # Fallback to default plan
                fallback_plan = self._get_default_plan()
                
                duration = time.time() - start_time
                self.logger.log_agent_complete(
                    "planner",
                    output_data={
                        "subtasks": fallback_plan,
                        "subtask_count": len(fallback_plan),
                        "fallback_used": True
                    },
                    duration_seconds=duration
                )
                
                # Return dict with fallback plan and data_quality
                return {
                    'plan': fallback_plan,
                    'data_quality': data_quality
                }
                
        except Exception as e:
            # Log unexpected error
            duration = time.time() - start_time
            self.logger.log_agent_error(
                "planner",
                error=e,
                context={
                    "user_query": user_query,
                    "duration_before_error": duration
                }
            )
            raise
    
    def _assess_data_quality(self, raw_data: Any, data_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess data quality characteristics to inform adaptive threshold selection
        
        Args:
            raw_data: pandas DataFrame (optional)
            data_summary: Dataset statistics
            
        Returns:
            Dictionary with quality metrics:
            - variance_level: 'high', 'medium', 'low'
            - cv_values: Coefficient of variation for key metrics
            - sample_size: Number of campaigns/data points
            - quality_level: Overall assessment
        """
        quality = {
            "variance_level": "medium",
            "cv_values": {},
            "sample_size": data_summary.get("campaigns", {}).get("count", 0),
            "quality_level": "medium"
        }
        
        # If raw data available, calculate actual CV
        if raw_data is not None:
            try:
                # Calculate coefficient of variation for key metrics
                for metric in ['ctr', 'roas', 'cvr']:
                    if metric in raw_data.columns:
                        values = raw_data[metric].dropna()
                        if len(values) > 0 and values.mean() != 0:
                            cv = values.std() / values.mean()
                            quality["cv_values"][metric] = cv
                
                # Determine variance level based on average CV
                if quality["cv_values"]:
                    avg_cv = np.mean(list(quality["cv_values"].values()))
                    
                    if avg_cv > self.high_variance_cv:
                        quality["variance_level"] = "high"
                    elif avg_cv < self.low_variance_cv:
                        quality["variance_level"] = "low"
                    else:
                        quality["variance_level"] = "medium"
                        
            except Exception as e:
                logger.warning(f"Could not calculate CV from raw data: {e}")
        
        # Use data summary as fallback
        else:
            # Heuristic: if small sample or large metric spread, assume high variance
            campaign_count = quality["sample_size"]
            avg_roas = data_summary.get("metrics", {}).get("avg_roas", 0)
            
            if campaign_count < 10:
                quality["variance_level"] = "high"
            elif avg_roas < 0.5 or avg_roas > 5.0:
                quality["variance_level"] = "high"
            else:
                quality["variance_level"] = "medium"
        
        # Set overall quality level
        if quality["variance_level"] == "high":
            quality["quality_level"] = "volatile"
        elif quality["variance_level"] == "low" and quality["sample_size"] > 50:
            quality["quality_level"] = "stable"
        else:
            quality["quality_level"] = "medium"
            
        return quality
    
    def _adapt_thresholds(self, data_quality: Dict[str, Any]) -> Dict[str, float]:
        """
        Adapt thresholds based on data quality assessment using ThresholdManager
        
        Args:
            data_quality: Output from _assess_data_quality
            
        Returns:
            Dictionary of adapted thresholds for different metrics
        """
        variance_level = data_quality["variance_level"]
        
        # Map variance_level to data_quality string for ThresholdManager
        quality_mapping = {
            "high": "volatile",
            "low": "stable",
            "medium": "medium"
        }
        quality_str = quality_mapping.get(variance_level, "medium")
        
        logger.info(f"Adapting thresholds for variance_level='{variance_level}' (quality='{quality_str}')")
        
        # Use ThresholdManager with priority resolution and adaptive multipliers
        thresholds = {
            "ctr_threshold": self.threshold_mgr.get_threshold(
                metric="ctr",
                data_quality=quality_str,
                use_adaptive=True
            ),
            "cvr_threshold": self.threshold_mgr.get_threshold(
                metric="cvr",
                data_quality=quality_str,
                use_adaptive=True
            ),
            "roas_threshold": self.threshold_mgr.get_threshold(
                metric="roas",
                data_quality=quality_str,
                use_adaptive=True
            )
        }
        
        return thresholds
    
    def _get_system_prompt(self) -> str:
        """System prompt defining planner role and output format"""
        return """You are a Marketing Analytics Planner Agent. Your job is to decompose user queries into structured subtasks.

**Your responsibilities:**
1. Understand what the user wants to know about Facebook ad performance
2. Break down the query into specific, actionable subtasks
3. Return a valid JSON structure

**Output format (strict JSON):**
{
  "subtasks": [
    {
      "task_id": "1",
      "task_type": "analyze_metric_trend",
      "description": "Analyze ROAS trend over time",
      "parameters": {
        "metric": "roas",
        "timeframe": "last_7_days"
      }
    },
    {
      "task_id": "2",
      "task_type": "identify_underperformers",
      "description": "Find campaigns with low CTR",
      "parameters": {
        "metric": "ctr",
        "threshold": 0.01
      }
    }
  ]
}

**Available task types:**
- analyze_metric_trend: Track how a metric changed over time
- identify_underperformers: Find low-performing campaigns/creatives
- segment_analysis: Compare performance across dimensions (platform, country, creative_type)
- creative_analysis: Analyze creative message effectiveness

**Available metrics (ONLY use these):**
- Base metrics: spend, impressions, clicks, purchases, revenue
- Calculated metrics: ctr, roas, cpc, cpm, cvr
- Aliases: sales (use 'revenue'), conversions (use 'purchases'), cost (use 'spend')

**CRITICAL: When user asks about "sales", use metric="revenue". When they ask about "conversions", use metric="purchases".**

**Rules:**
- Always output valid JSON
- Include 2-4 subtasks
- Be specific in descriptions
- Use ONLY metrics from the list above
- Set reasonable parameters based on the data summary"""

    def _build_prompt(self, user_query: str, data_summary: Dict[str, Any], 
                      adaptive_thresholds: Dict[str, float], data_quality: Dict[str, Any]) -> str:
        """Build prompt with query, context, and adaptive thresholds"""
        return f"""User Query: "{user_query}"

Dataset Context:
- Date Range: {data_summary['date_range']['start']} to {data_summary['date_range']['end']} ({data_summary['date_range']['days']} days)
- Total Campaigns: {data_summary['campaigns']['count']}
- Total Spend: ${data_summary['metrics']['total_spend']:,.2f}
- Average ROAS: {data_summary['metrics']['avg_roas']:.2f}
- Average CTR: {data_summary['metrics']['avg_ctr']:.2%}

Data Quality Assessment:
- Variance Level: {data_quality['quality_level']}
- Sample Size: {data_quality['sample_size']} campaigns

Adaptive Thresholds (adjusted for data characteristics):
- CTR Threshold: {adaptive_thresholds['ctr_threshold']:.4f}
- CVR Threshold: {adaptive_thresholds['cvr_threshold']:.4f}
- ROAS Threshold: {adaptive_thresholds['roas_threshold']:.2f}

Available Dimensions:
- Creative Types: {list(data_summary['dimensions']['creative_types'].keys())}
- Platforms: {list(data_summary['dimensions']['platforms'].keys())}
- Countries: {list(data_summary['dimensions']['countries'].keys())}

Generate a structured plan with 2-4 subtasks to answer this query. Use the adaptive thresholds above when setting parameters for underperformer identification. Output ONLY valid JSON, no other text."""

    def _get_default_plan(self) -> List[Dict[str, Any]]:
        """Fallback plan if LLM fails - uses ThresholdManager"""
        logger.warning("Using default fallback plan with ThresholdManager")
        
        # Get threshold from ThresholdManager (no adaptive, just base)
        ctr_threshold = self.threshold_mgr.get_threshold(metric="ctr", use_adaptive=False)
        
        return [
            {
                "task_id": "1",
                "task_type": "analyze_metric_trend",
                "description": "Analyze ROAS trend over time",
                "parameters": {"metric": "roas", "timeframe": "last_7_days"}
            },
            {
                "task_id": "2",
                "task_type": "identify_underperformers",
                "description": "Find campaigns with low CTR",
                "parameters": {"metric": "ctr", "threshold": ctr_threshold}
            }
        ]
