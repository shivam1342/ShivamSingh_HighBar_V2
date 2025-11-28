"""
Insight Agent - Generates hypotheses explaining performance patterns
"""
import json
import logging
from typing import Dict, List, Any
from src.utils.llm import LLMClient

logger = logging.getLogger(__name__)


class InsightAgent:
    """
    Generates data-driven hypotheses about performance patterns
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
    def generate_insights(
        self,
        analysis_results: List[Dict[str, Any]],
        data_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate insights from analysis results
        
        Args:
            analysis_results: Results from data agent subtasks
            data_context: Overall dataset context
            
        Returns:
            List of insights with hypotheses and evidence
        """
        logger.info("Generating insights from analysis results")
        
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_prompt(analysis_results, data_context)
        
        response = self.llm.generate(user_prompt, system_prompt)
        
        try:
            # Extract JSON from markdown code blocks if present
            clean_response = response
            if "```json" in response:
                clean_response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                clean_response = response.split("```")[1].split("```")[0].strip()
            
            insights = json.loads(clean_response)
            logger.info(f"Generated {len(insights.get('insights', []))} insights")
            return insights.get("insights", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse insights response: {e}")
            return self._get_fallback_insights(analysis_results)
    
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
        data_context: Dict[str, Any]
    ) -> str:
        """Build prompt with analysis results and context"""
        
        # Summarize analysis results
        results_summary = []
        for i, result in enumerate(analysis_results, 1):
            results_summary.append(f"Analysis {i}: {json.dumps(result, indent=2)}")
        
        return f"""Based on the following analysis results, generate 2-4 key insights explaining what's happening with this Facebook Ads account.

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
