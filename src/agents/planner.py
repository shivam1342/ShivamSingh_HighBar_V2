"""
Planner Agent - Decomposes user query into actionable subtasks
"""
import json
import logging
from typing import Dict, List, Any
from src.utils.llm import LLMClient

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Decomposes high-level queries into structured subtasks
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
    def plan(self, user_query: str, data_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create execution plan from user query
        
        Args:
            user_query: Natural language query from user
            data_summary: High-level dataset statistics
            
        Returns:
            List of subtasks with type and parameters
        """
        logger.info(f"Planning for query: {user_query}")
        
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_prompt(user_query, data_summary)
        
        response = self.llm.generate(user_prompt, system_prompt)
        
        try:
            # Parse JSON response
            plan = json.loads(response)
            logger.info(f"Generated plan with {len(plan.get('subtasks', []))} subtasks")
            return plan.get("subtasks", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse planner response: {e}")
            # Fallback to default plan
            return self._get_default_plan()
    
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

**Rules:**
- Always output valid JSON
- Include 2-4 subtasks
- Be specific in descriptions
- Set reasonable parameters based on the data summary"""

    def _build_prompt(self, user_query: str, data_summary: Dict[str, Any]) -> str:
        """Build prompt with query and context"""
        return f"""User Query: "{user_query}"

Dataset Context:
- Date Range: {data_summary['date_range']['start']} to {data_summary['date_range']['end']} ({data_summary['date_range']['days']} days)
- Total Campaigns: {data_summary['campaigns']['count']}
- Total Spend: ${data_summary['metrics']['total_spend']:,.2f}
- Average ROAS: {data_summary['metrics']['avg_roas']:.2f}
- Average CTR: {data_summary['metrics']['avg_ctr']:.2%}

Available Dimensions:
- Creative Types: {list(data_summary['dimensions']['creative_types'].keys())}
- Platforms: {list(data_summary['dimensions']['platforms'].keys())}
- Countries: {list(data_summary['dimensions']['countries'].keys())}

Generate a structured plan with 2-4 subtasks to answer this query. Output ONLY valid JSON, no other text."""

    def _get_default_plan(self) -> List[Dict[str, Any]]:
        """Fallback plan if LLM fails"""
        logger.warning("Using default fallback plan")
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
                "parameters": {"metric": "ctr", "threshold": 0.01}
            }
        ]
