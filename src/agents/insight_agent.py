"""
Insight Agent - Generates hypotheses explaining performance patterns
"""
import json
import logging
import time
from typing import Dict, List, Any, Optional
from src.utils.llm import LLMClient
from src.utils.structured_logger import StructuredLogger
from src.utils.exceptions import JSONParseError
from src.monitoring.alert_manager import AlertManager, AlertSeverity

logger = logging.getLogger(__name__)


class InsightAgent:
    """
    Generates data-driven hypotheses about performance patterns
    """
    
    def __init__(
        self, 
        llm_client: LLMClient, 
        structured_logger: StructuredLogger = None,
        alert_manager: Optional[AlertManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.llm = llm_client
        self.logger = structured_logger or StructuredLogger()
        self.alert_manager = alert_manager
        self.config = config or {}
        
        # Get confidence threshold from config
        self.confidence_threshold = self.config.get('monitoring', {}).get('alerts', {}).get('confidence_threshold', 0.5)
        
    def generate_insights(
        self,
        analysis_results: List[Dict[str, Any]],
        data_context: Dict[str, Any],
        user_query: str = None
    ) -> List[Dict[str, Any]]:
        """
        Generate insights from analysis results
        
        Args:
            analysis_results: Results from data agent subtasks
            data_context: Overall dataset context
            user_query: Original user question to focus insights
            
        Returns:
            List of insights with hypotheses and evidence
        """
        # Log agent start
        self.logger.log_agent_start(
            "insight_agent",
            input_data={
                "analysis_result_count": len(analysis_results),
                "data_context_keys": list(data_context.keys())
            }
        )
        
        start_time = time.time()
        
        try:
            logger.info("Generating insights from analysis results")
            
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_prompt(analysis_results, data_context, user_query)
            
            # Log LLM call
            llm_start = time.time()
            response = self.llm.generate(user_prompt, system_prompt)
            llm_duration = time.time() - llm_start
            
            self.logger.log_llm_call(
                agent_name="insight_agent",
                prompt=user_prompt,
                system_prompt=system_prompt,
                response=response,
                model=self.llm.model,
                duration_seconds=llm_duration
            )
            
            try:
                # Extract JSON from markdown code blocks if present
                clean_response = response
                if "```json" in response:
                    clean_response = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    clean_response = response.split("```")[1].split("```")[0].strip()
                
                insights = json.loads(clean_response)
                insight_list = insights.get("insights", [])
                
                logger.info(f"Generated {len(insight_list)} insights")
                
                # Check for low confidence insights and raise alerts
                if self.alert_manager:
                    self._check_insight_confidence(insight_list)
                
                # Log metrics for confidence scores
                if insight_list:
                    avg_confidence = sum(i.get("confidence", 0) for i in insight_list) / len(insight_list)
                    self.logger.log_metric(
                        "insight_confidence",
                        avg_confidence,
                        context={
                            "insight_count": len(insight_list),
                            "min_confidence": min(i.get("confidence", 0) for i in insight_list),
                            "max_confidence": max(i.get("confidence", 0) for i in insight_list)
                        }
                    )
                
                # Log completion
                duration = time.time() - start_time
                self.logger.log_agent_complete(
                    "insight_agent",
                    output_data={
                        "insight_count": len(insight_list),
                        "categories": [i.get("category") for i in insight_list]
                    },
                    duration_seconds=duration
                )
                
                return insight_list
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse insights response: {e}")
                
                # Log JSON parse error
                self.logger.log_agent_error(
                    "insight_agent",
                    error=JSONParseError(
                        f"Failed to parse JSON from LLM response: {e}",
                        raw_response=response,
                        agent_name="insight_agent"
                    ),
                    context={"raw_response": response[:500]}
                )
                
                # Fallback
                fallback = self._get_fallback_insights(analysis_results)
                
                duration = time.time() - start_time
                self.logger.log_agent_complete(
                    "insight_agent",
                    output_data={
                        "insight_count": len(fallback),
                        "fallback_used": True
                    },
                    duration_seconds=duration
                )
                
                return fallback
                
        except Exception as e:
            # Log unexpected error
            duration = time.time() - start_time
            self.logger.log_agent_error(
                "insight_agent",
                error=e,
                context={
                    "analysis_result_count": len(analysis_results),
                    "duration_before_error": duration
                }
            )
            raise
    
    def _get_system_prompt(self) -> str:
        """System prompt for insight generation"""
        return """You are a Senior Marketing Analytics Expert. Your job is to analyze Facebook Ads data and generate actionable insights.

**Your Process:**
1. **THINK**: Review the data patterns and numbers
2. **ANALYZE**: Identify what's driving performance changes
3. **CONCLUDE**: Form clear, testable hypotheses

**Output Format (strict JSON):**
{
  "insights": [
    {
      "id": "insight_1",
      "category": "roas_decline",
      "hypothesis": "ROAS declined 23% in the last 7 days due to audience fatigue in Retargeting campaigns",
      "evidence": [
        "Retargeting campaigns show 18% CTR drop",
        "Impressions increased 40% while clicks stayed flat",
        "Best performing period was days 1-10, now seeing diminishing returns"
      ],
      "confidence": 0.75,
      "reasoning": "The correlation between increased frequency and declining CTR suggests audience saturation. Retargeting audiences are smaller and exhaust faster.",
      "recommendation": "Pause underperforming retargeting campaigns and refresh creative OR expand to LAL audiences"
    }
  ]
}

**Categories:**
- roas_decline / roas_improvement
- ctr_issues
- creative_fatigue
- audience_saturation
- platform_performance
- budget_allocation

**Rules:**
- Base hypotheses ONLY on provided data
- Include specific numbers as evidence
- Confidence must be 0.0 to 1.0 (be honest about uncertainty)
- Each insight needs clear reasoning
- Recommendations must be actionable
- Output ONLY valid JSON"""

    def _build_prompt(
        self,
        analysis_results: List[Dict[str, Any]],
        data_context: Dict[str, Any],
        user_query: str = None
    ) -> str:
        """Build prompt with analysis results, context, and user query"""
        
        # Summarize analysis results
        results_summary = []
        for i, result in enumerate(analysis_results, 1):
            results_summary.append(f"Analysis {i}: {json.dumps(result, indent=2)}")
        
        query_context = f"\n**USER QUESTION:** {user_query}\n**IMPORTANT:** Your insights MUST directly answer this question. Focus your analysis on what the user asked.\n" if user_query else ""
        
        return f"""Based on the following analysis results, generate 2-4 key insights explaining what's happening with this Facebook Ads account.
{query_context}
**Data Context:**
- Date Range: {data_context['summary']['date_range']['start']} to {data_context['summary']['date_range']['end']}
- Total Spend: ${data_context['summary']['metrics']['total_spend']:,.2f}
- Total Revenue: ${data_context['summary']['metrics']['total_revenue']:,.2f}
- Average ROAS: {data_context['summary']['metrics']['avg_roas']:.2f}
- Average CTR: {data_context['summary']['metrics']['avg_ctr']:.2%}

**Time Series Context:**
- Recent ROAS: {data_context['time_series']['recent_avg']:.2f}
- Previous ROAS: {data_context['time_series']['previous_avg']:.2f}
- Change: {data_context['time_series']['change_pct']:.1f}%

**Analysis Results:**
{chr(10).join(results_summary)}

Generate insights that:
1. Explain WHY performance changed
2. Identify root causes (creative fatigue, audience issues, etc.)
3. Include specific evidence from the data
4. Provide actionable recommendations

Output ONLY valid JSON with 2-4 insights. Think step by step."""

    def _get_fallback_insights(self, analysis_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate basic insights if LLM fails"""
        logger.warning("Using fallback insights")
        
        insights = []
        
        # Try to extract at least one insight from results
        for result in analysis_results:
            if 'change_pct' in result:
                insights.append({
                    "id": "fallback_1",
                    "category": "metric_change",
                    "hypothesis": f"Metric {result.get('metric', 'unknown')} changed by {result.get('change_pct', 0):.1f}%",
                    "evidence": [f"Recent average: {result.get('recent_avg', 0):.2f}"],
                    "confidence": 0.5,
                    "reasoning": "Basic statistical observation",
                    "recommendation": "Investigate further to understand root cause"
                })
        
        if not insights:
            insights.append({
                "id": "fallback_generic",
                "category": "general",
                "hypothesis": "Performance metrics require attention",
                "evidence": ["Analysis completed but pattern unclear"],
                "confidence": 0.3,
                "reasoning": "Insufficient data for conclusive insights",
                "recommendation": "Review detailed metrics and run targeted analysis"
            })
        
        return insights
    
    def _check_insight_confidence(self, insights: List[Dict[str, Any]]) -> None:
        """
        Check insights for low confidence and raise alerts.
        
        Args:
            insights: List of insights to check
        """
        for insight in insights:
            confidence = insight.get('confidence', 0)
            insight_id = insight.get('insight_id', insight.get('id', 'unknown'))
            
            if confidence < self.confidence_threshold:
                # Determine reason for low confidence
                evidence_count = len(insight.get('evidence', []))
                if evidence_count < 2:
                    reason = f"Insufficient evidence (only {evidence_count} point(s))"
                else:
                    reason = "Low confidence despite evidence - data may be volatile"
                
                # Raise alert
                self.alert_manager.add_low_confidence_alert(
                    insight_id=insight_id,
                    confidence=confidence,
                    threshold=self.confidence_threshold,
                    reason=reason
                )
                
                logger.warning(
                    f"⚠️  Low confidence insight: '{insight_id}' "
                    f"(confidence: {confidence:.2f}, threshold: {self.confidence_threshold})"
                )
