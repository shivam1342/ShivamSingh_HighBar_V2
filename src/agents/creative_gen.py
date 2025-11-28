"""
Creative Generator Agent - Produces new creative recommendations for low-CTR campaigns
"""
import json
import logging
from typing import Dict, List, Any
import pandas as pd
from src.utils.llm import LLMClient

logger = logging.getLogger(__name__)


class CreativeGeneratorAgent:
    """
    Generates new creative ideas based on performance patterns
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
    def generate_creatives(
        self,
        underperformers: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        dataset_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate creative recommendations for underperforming campaigns
        
        Args:
            underperformers: Low-CTR campaigns/creatives
            top_performers: High-CTR campaigns for learning
            dataset_context: Overall dataset info
            
        Returns:
            List of creative recommendations with variations
        """
        logger.info("Generating creative recommendations")
        
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_prompt(underperformers, top_performers, dataset_context)
        
        response = self.llm.generate(user_prompt, system_prompt)
        
        try:
            # Extract JSON from markdown code blocks if present
            clean_response = response
            if "```json" in response:
                clean_response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                clean_response = response.split("```")[1].split("```")[0].strip()
            
            creatives = json.loads(clean_response)
            logger.info(f"Generated {len(creatives.get('recommendations', []))} creative recommendations")
            return creatives.get("recommendations", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse creative recommendations: {e}")
            return self._get_fallback_creatives(underperformers)
    
    def _get_system_prompt(self) -> str:
        """System prompt for creative generation"""
        return """You are a Senior Creative Strategist specializing in direct-response Facebook ads. Your job is to generate new creative concepts for underperforming campaigns.

**Your Process:**
1. **ANALYZE**: Study what works (high CTR creatives) and what doesn't
2. **IDENTIFY**: Find patterns in messaging, hooks, and CTAs
3. **CREATE**: Generate new variations addressing weaknesses

**Output Format (strict JSON):**
{
  "recommendations": [
    {
      "campaign": "Men ComfortMax Launch",
      "adset": "Adset-1 Retarget",
      "current_issue": "Generic messaging, low emotional appeal, CTR 0.8%",
      "creative_variations": [
        {
          "variation_id": "var_1",
          "creative_type": "UGC",
          "headline": "Finally, boxers that don't ride up",
          "message": "Tested by 10,000+ men. Zero complaints about ride-up. 60-day guarantee.",
          "cta": "Try Risk-Free",
          "rationale": "Addresses specific pain point with social proof and risk reversal",
          "expected_improvement": "30-50% CTR lift based on similar winning patterns"
        }
      ],
      "testing_strategy": "Start with UGC format, test 3 variations, $50/day per ad"
    }
  ]
}

**Creative Principles:**
- Lead with specific benefits, not features
- Use social proof (testimonials, numbers)
- Address pain points directly
- Create urgency (limited time, scarcity)
- Match creative type to message (UGC for authenticity, Video for demos)

**Rules:**
- Base recommendations on actual top-performing patterns
- Generate 2-3 variations per campaign
- Each variation must be distinct (different angle/hook)
- Include specific rationale for each creative choice
- Output ONLY valid JSON"""

    def _build_prompt(
        self,
        underperformers: List[Dict[str, Any]],
        top_performers: List[Dict[str, Any]],
        dataset_context: Dict[str, Any]
    ) -> str:
        """Build prompt with performance data and patterns"""
        
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

Generate 3-5 creative recommendations that:
1. Address specific weaknesses in underperforming campaigns
2. Apply patterns from top performers
3. Include multiple variations per campaign
4. Provide clear testing strategy

Output ONLY valid JSON. Be creative but grounded in data patterns."""

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
