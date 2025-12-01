"""
Planner Agent - Decomposes user query into actionable subtasks
"""
import json
import logging
import time
from typing import Dict, List, Any
from src.utils.llm import LLMClient
from src.utils.structured_logger import StructuredLogger
from src.utils.exceptions import JSONParseError

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Decomposes high-level queries into structured subtasks
    """
    
    def __init__(self, llm_client: LLMClient, structured_logger: StructuredLogger = None):
        self.llm = llm_client
        self.logger = structured_logger or StructuredLogger()
        
    def plan(self, user_query: str, data_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create execution plan from user query
        
        Args:
            user_query: Natural language query from user
            data_summary: High-level dataset statistics
            
        Returns:
            List of subtasks with type and parameters
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
            
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_prompt(user_query, data_summary)
            
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
                        "subtask_count": len(subtasks)
                    },
                    duration_seconds=duration
                )
                
                return subtasks
                
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
                
                return fallback_plan
                
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
