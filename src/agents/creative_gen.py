"""
Creative Generator Agent - Produces new creative recommendations for low-CTR campaigns
"""
import json
import logging
import time
from typing import Dict, List, Any
import pandas as pd
from src.utils.llm import LLMClient
from src.utils.structured_logger import StructuredLogger
from src.utils.exceptions import JSONParseError

logger = logging.getLogger(__name__)


class CreativeGeneratorAgent:
    """
    Generates new creative ideas based on performance patterns
    """
    
    def __init__(self, llm_client: LLMClient, structured_logger: StructuredLogger = None):
        self.llm = llm_client
        self.logger = structured_logger or StructuredLogger()
        
    def generate_creatives(
        self,
        underperformers: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        dataset_context: Dict[str, Any],
        validated_insights: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate creative recommendations for underperforming campaigns
        
        Args:
            underperformers: Low-CTR campaigns/creatives
            top_performers: High-CTR campaigns for learning
            dataset_context: Overall dataset info
            validated_insights: Insights from InsightAgent to build upon
            
        Returns:
            List of creative recommendations with variations
        """
        # Log agent start
        self.logger.log_agent_start(
            "creative_generator",
            input_data={
                "underperformer_count": len(underperformers),
                "top_performer_count": len(top_performers)
            }
        )
        
        start_time = time.time()
        
        try:
            logger.info("Generating creative recommendations")
            
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_prompt(underperformers, top_performers, dataset_context, validated_insights or [])
            
            # Log LLM call
            llm_start = time.time()
            response = self.llm.generate(user_prompt, system_prompt)
            llm_duration = time.time() - llm_start
            
            self.logger.log_llm_call(
                agent_name="creative_generator",
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
                
                creatives = json.loads(clean_response)
                recommendations = creatives.get("recommendations", [])
                
                logger.info(f"Generated {len(recommendations)} creative recommendations")
                
                # Log completion
                duration = time.time() - start_time
                self.logger.log_agent_complete(
                    "creative_generator",
                    output_data={
                        "recommendation_count": len(recommendations),
                        "campaigns_addressed": list(set(r.get("campaign") for r in recommendations))
                    },
                    duration_seconds=duration
                )
                
                return recommendations
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse creative recommendations: {e}")
                
                # Log JSON parse error
                self.logger.log_agent_error(
                    "creative_generator",
                    error=JSONParseError(
                        f"Failed to parse JSON from LLM response: {e}",
                        raw_response=response,
                        agent_name="creative_generator"
                    ),
                    context={"raw_response": response[:500]}
                )
                
                # Fallback
                fallback = self._get_fallback_creatives(underperformers)
                
                duration = time.time() - start_time
                self.logger.log_agent_complete(
                    "creative_generator",
                    output_data={
                        "recommendation_count": len(fallback),
                        "fallback_used": True
                    },
                    duration_seconds=duration
                )
                
                return fallback
                
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            self.logger.log_agent_error(
                "creative_generator",
                error=e,
                context={
                    "underperformer_count": len(underperformers),
                    "duration_before_error": duration
                }
            )
            raise
    
    def _get_system_prompt(self) -> str:
        """System prompt for creative generation"""
        return """You are a Senior Creative Strategist specializing in direct-response Facebook ads. Your job is to generate SPECIFIC creative concepts that implement validated insights.

**CRITICAL: You will receive validated insights from the analysis. Your job is to CREATE ACTUAL AD CONCEPTS that implement those insights, NOT to repeat the insights.**

Example:
❌ BAD: "Rotate ad creative regularly to avoid fatigue" (this just repeats the insight)
✅ GOOD: "Create 3 UGC video variations featuring customer testimonials with fresh angles: comfort, durability, and style" (this implements the insight)

**Your Process:**
1. **READ INSIGHTS**: Understand what the data revealed (e.g., "audience fatigue on Retargeting")
2. **IDENTIFY ROOT CAUSE**: What's causing the issue? (e.g., "same ad shown 15+ times")
3. **CREATE SOLUTIONS**: Design specific ads that fix the issue (e.g., "3 new creative angles to refresh messaging")

**Output Format (strict JSON):**
{
  "recommendations": [
    {
      "campaign": "Men ComfortMax Launch",
      "adset": "Adset-1 Retarget",
      "current_issue": "Audience fatigue - same creative shown 15+ times, CTR dropped 40%",
      "insight_addressed": "insight_1: Retargeting audience saturated",
      "creative_variations": [
        {
          "variation_id": "var_1",
          "creative_type": "UGC",
          "headline": "Still thinking about ComfortMax?",
          "message": "Join 10,000+ men who made the switch. Here's what they're saying...",
          "cta": "See Reviews",
          "rationale": "Fresh angle for retargeting - social proof instead of product features",
          "expected_improvement": "30-50% CTR recovery"
        }
      ],
      "testing_strategy": "Launch 3 variations simultaneously, $40/day each, rotate every 5 days"
    }
  ]
}

**Creative Principles:**
- Lead with specific benefits, not features
- Use social proof (testimonials, numbers)
- Address pain points directly
- Create urgency when appropriate
- Match creative type to message (UGC for authenticity, Video for demos)

**Rules:**
- Each recommendation must reference which insight it addresses
- Use ACTUAL campaign/adset names from underperformers
- Generate 2-3 variations per campaign (each with different angle)
- Include specific headlines, messages, and CTAs
- Provide clear rationale tied to insights
- Output ONLY valid JSON"""

    def _build_prompt(
        self,
        underperformers: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        dataset_context: Dict[str, Any],
        validated_insights: List[Dict[str, Any]]
    ) -> str:
        """Build prompt with performance data, patterns, and validated insights"""
        
        # Extract key insights to inform creative strategy
        insight_summary = []
        if validated_insights:
            for insight in validated_insights[:3]:  # Top 3 insights
                insight_summary.append(f"- **{insight.get('category', 'insight')}**: {insight.get('hypothesis', 'N/A')}")
                if 'recommendation' in insight:
                    insight_summary.append(f"  Recommendation: {insight['recommendation']}")
        
        insight_context = "\n".join(insight_summary) if insight_summary else "No validated insights available"
        
        # Extract messaging patterns from top performers
        top_messages = []
        if 'top_performers' in top_performers:
            for perf in top_performers['top_performers'][:5]:
                top_messages.append({
                    "message": perf.get("creative_message", ""),
                    "type": perf.get("creative_type", ""),
                    "ctr": perf.get("ctr", 0)
                })
        
        # Focus on worst underperformers
        worst_performers = []
        if 'top_underperformers' in underperformers:
            for under in underperformers['top_underperformers'][:5]:
                worst_performers.append({
                    "campaign": under.get("campaign_name", ""),
                    "adset": under.get("adset_name", ""),
                    "ctr": under.get("ctr", 0),
                    "spend": under.get("spend", 0)
                })
        
        return f"""Generate creative recommendations for underperforming campaigns in this Facebook Ads account.

**VALIDATED INSIGHTS FROM ANALYSIS:**
{insight_context}

**IMPORTANT:** Your creative recommendations must DIRECTLY ADDRESS the insights above. Don't just repeat the recommendations - create specific ad variations that implement them.

**Account Context:**
- Product Category: Undergarments (Men's & Women's)
- Target Audience: Comfort-seeking, quality-conscious consumers
- Current Avg CTR: {dataset_context['summary']['metrics']['avg_ctr']:.2%}

**Top Performing Creatives (Learn from these):**
{json.dumps(top_messages, indent=2)}

**Underperforming Campaigns (Need improvement):**
{json.dumps(worst_performers, indent=2)}

**What's Working:**
- High CTR creative types: {list(dataset_context.get('dimensions', {}).get('creative_types', {}).keys())}
- Best performing platforms: {list(dataset_context.get('dimensions', {}).get('platforms', {}).keys())}

**Your Task:**
Generate 2-3 creative recommendations that:
1. **Implement the validated insights** (e.g., if insight says "audience fatigue", create fresh angles)
2. **Use actual campaign/adset names** from underperformers list
3. **Apply patterns from top performers** (creative types, messaging styles)
4. **Provide actionable, specific creative variations** (headlines, messages, CTAs)
5. **Don't repeat insight recommendations** - create actual ad concepts!

Output ONLY valid JSON. Be specific and actionable."""

    def _get_fallback_creatives(self, underperformers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate basic creative recommendations if LLM fails"""
        logger.warning("Using fallback creative recommendations")
        
        recommendations = []
        
        if 'top_underperformers' in underperformers:
            for under in underperformers['top_underperformers'][:3]:
                recommendations.append({
                    "campaign": under.get("campaign_name", "Unknown"),
                    "adset": under.get("adset_name", "Unknown"),
                    "current_issue": f"Low CTR: {under.get('ctr', 0):.2%}",
                    "creative_variations": [
                        {
                            "variation_id": "fallback_1",
                            "creative_type": "UGC",
                            "headline": "Try our best-selling product",
                            "message": "Join thousands of satisfied customers",
                            "cta": "Shop Now",
                            "rationale": "Generic recommendation - requires manual refinement",
                            "expected_improvement": "Unknown - test required"
                        }
                    ],
                    "testing_strategy": "A/B test with $50/day budget"
                })
        
        return recommendations
