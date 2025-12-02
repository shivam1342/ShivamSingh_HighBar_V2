"""
Orchestrator - Main agent coordination logic
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from src.agents.planner import PlannerAgent
from src.agents.data_agent import DataAgent
from src.agents.insight_agent import InsightAgent
from src.agents.evaluator import EvaluatorAgent
from src.agents.creative_gen import CreativeGeneratorAgent
from src.utils.llm import LLMClient
from src.utils.data_loader import DataLoader
from src.utils.structured_logger import StructuredLogger

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Coordinates the multi-agent workflow:
    Planner → Data Agent → Insight Agent → Evaluator → Creative Generator
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_retries = 2
        
        # Initialize structured logger
        self.logger = StructuredLogger()
        
        # Initialize LLM client
        self.llm_client = LLMClient(config["llm"])
        
        # Initialize data loader
        data_config = config["data"]
        self.data_loader = DataLoader(
            csv_path=data_config["csv_path"],
            use_sample=data_config.get("use_sample", False),
            sample_size=data_config.get("sample_size", 1000)
        )
        
        # Initialize agents (pass structured logger and config)
        self.planner = PlannerAgent(self.llm_client, config, self.logger)
        self.data_agent = DataAgent(self.data_loader, self.logger)
        self.insight_agent = InsightAgent(self.llm_client, self.logger)
        self.evaluator = EvaluatorAgent(config, self.logger)
        self.creative_gen = CreativeGeneratorAgent(self.llm_client, self.logger)
        
        # Initialize data agent
        self.data_agent.initialize()
        
    def run(self, user_query: str) -> Dict[str, Any]:
        """
        Execute the full agent pipeline
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            Complete results including insights, creatives, and logs
        """
        # Log orchestration start
        self.logger.log_agent_start(
            "orchestrator",
            input_data={"user_query": user_query}
        )
        
        pipeline_start = time.time()
        
        try:
            logger.info(f"Starting orchestration for query: {user_query}")
            
            # Step 1: Get data summary
            step1_start = time.time()
            data_summary = self.data_loader.get_summary()
            self.logger.log_data_summary("dataset_overview", data_summary)
            logger.info(f"Step 1 completed in {time.time() - step1_start:.2f}s")
            
            # Step 2: Planner creates execution plan (with raw data for quality assessment)
            step2_start = time.time()
            raw_data = self.data_loader.df  # Pass raw DataFrame for CV calculation
            plan = self.planner.plan(user_query, data_summary, raw_data)
            logger.info(f"Step 2 completed in {time.time() - step2_start:.2f}s")
            
            # Step 3: Data agent executes subtasks
            step3_start = time.time()
            analysis_results = []
            for subtask in plan:
                result = self.data_agent.execute_subtask(subtask)
                analysis_results.append(result)
            logger.info(f"Step 3 completed in {time.time() - step3_start:.2f}s")
            
            # Step 4: Insight agent generates hypotheses (with retry logic)
            step4_start = time.time()
            data_context = self.data_agent.get_context_for_insights()
            insights = None
            evaluation = None
            
            for attempt in range(self.max_retries):
                logger.info(f"Insight generation attempt {attempt + 1}/{self.max_retries}")
                
                # Log retry attempt if not first attempt
                if attempt > 0:
                    self.logger.log_retry_attempt(
                        agent_name="orchestrator",
                        attempt_number=attempt + 1,
                        max_attempts=self.max_retries,
                        reason="Insights failed validation",
                        next_delay_seconds=0
                    )
                
                insights = self.insight_agent.generate_insights(analysis_results, data_context, user_query)
                
                # Step 5: Evaluator validates insights
                evaluation = self.evaluator.evaluate_insights(insights, analysis_results)
                
                # Check if we need to retry
                if not self.evaluator.requires_retry(evaluation):
                    logger.info("Insights passed evaluation")
                    break
                else:
                    logger.warning(f"Insights failed evaluation, retrying... (attempt {attempt + 1})")
            
            logger.info(f"Steps 4-5 completed in {time.time() - step4_start:.2f}s")
            
            # Use validated insights
            validated_insights = evaluation.get("validated_insights", insights)
            
            # Step 6: Creative generator produces recommendations (for low-CTR campaigns)
            step6_start = time.time()
            # Find underperformer and top performer data
            underperformer_data = {}
            creative_analysis = {}
            
            for result in analysis_results:
                if "top_underperformers" in result:
                    underperformer_data = result
                if "top_performers" in result:
                    creative_analysis = result
            
            creatives = self.creative_gen.generate_creatives(
                underperformer_data,
                creative_analysis,
                data_context,
                validated_insights  # Pass insights so creatives build on them!
            )
            logger.info(f"Step 6 completed in {time.time() - step6_start:.2f}s")
            
            # Step 7: Compile final results
            results = {
                "query": user_query,
                "execution_time": datetime.now().isoformat(),
                "plan": plan,
                "analysis_results": analysis_results,
                "insights": validated_insights,
                "evaluation": evaluation,
                "creative_recommendations": creatives
            }
            
            # Log orchestration completion
            pipeline_duration = time.time() - pipeline_start
            self.logger.log_agent_complete(
                "orchestrator",
                output_data={
                    "insight_count": len(validated_insights),
                    "creative_count": len(creatives),
                    "quality_score": evaluation.get("overall_quality", 0),
                    "passed_validation": evaluation.get("pass_threshold", False)
                },
                duration_seconds=pipeline_duration
            )
            
            logger.info(f"Orchestration complete in {pipeline_duration:.2f}s")
            
            return results
            
        except Exception as e:
            # Log orchestration error
            pipeline_duration = time.time() - pipeline_start
            self.logger.log_agent_error(
                "orchestrator",
                error=e,
                context={
                    "user_query": user_query,
                    "duration_before_error": pipeline_duration
                }
            )
            raise
        
    def save_outputs(self, results: Dict[str, Any]):
        """Save insights, creatives, and report to files"""
        outputs_config = self.config["outputs"]
        
        # Ensure directories exist
        Path(outputs_config["reports_dir"]).mkdir(exist_ok=True)
        Path(outputs_config["logs_dir"]).mkdir(exist_ok=True)
        
        # Save insights.json
        insights_path = Path(outputs_config["insights_file"])
        with open(insights_path, 'w') as f:
            json.dump(results["insights"], f, indent=2)
        logger.info(f"Saved insights to {insights_path}")
        
        # Save creatives.json
        creatives_path = Path(outputs_config["creatives_file"])
        with open(creatives_path, 'w') as f:
            json.dump(results["creative_recommendations"], f, indent=2)
        logger.info(f"Saved creatives to {creatives_path}")
        
        # Save report.md
        report_path = Path(outputs_config["report_file"])
        report_content = self._generate_report(results)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        logger.info(f"Saved report to {report_path}")
        
        logger.info(f"Structured logs saved to {outputs_config['logs_dir']}/execution.jsonl")
    
    def _generate_report(self, results: Dict[str, Any]) -> str:
        """Generate markdown report for marketers"""
        report = f"""# Facebook Ads Performance Analysis Report

**Generated:** {results["execution_time"]}  
**Query:** {results["query"]}

---

## Executive Summary

This report analyzes Facebook Ads performance for the undergarments campaign, identifying key drivers of ROAS changes and providing actionable creative recommendations.

## Key Insights

"""
        
        # Add insights
        for i, insight in enumerate(results["insights"], 1):
            conf_pct = insight.get("confidence", 0) * 100
            report += f"### {i}. {insight.get('hypothesis', 'N/A')}\n\n"
            report += f"**Confidence:** {conf_pct:.0f}%  \n"
            report += f"**Category:** {insight.get('category', 'N/A')}\n\n"
            
            report += "**Evidence:**\n"
            for evidence in insight.get("evidence", []):
                report += f"- {evidence}\n"
            report += "\n"
            
            report += f"**Reasoning:** {insight.get('reasoning', 'N/A')}\n\n"
            report += f"**Recommendation:** {insight.get('recommendation', 'N/A')}\n\n"
            report += "---\n\n"
        
        # Add creative recommendations
        report += "## Creative Recommendations\n\n"
        
        for i, creative in enumerate(results["creative_recommendations"], 1):
            report += f"### Campaign: {creative.get('campaign', 'N/A')}\n\n"
            report += f"**Current Issue:** {creative.get('current_issue', 'N/A')}\n\n"
            
            report += "**New Creative Variations:**\n\n"
            for var in creative.get("creative_variations", []):
                report += f"#### Variation {var.get('variation_id', 'N/A')}\n\n"
                report += f"- **Type:** {var.get('creative_type', 'N/A')}\n"
                report += f"- **Headline:** {var.get('headline', 'N/A')}\n"
                report += f"- **Message:** {var.get('message', 'N/A')}\n"
                report += f"- **CTA:** {var.get('cta', 'N/A')}\n"
                report += f"- **Rationale:** {var.get('rationale', 'N/A')}\n"
                report += f"- **Expected Impact:** {var.get('expected_improvement', 'N/A')}\n\n"
            
            report += f"**Testing Strategy:** {creative.get('testing_strategy', 'N/A')}\n\n"
            report += "---\n\n"
        
        # Add evaluation quality
        if "evaluation" in results:
            eval_data = results["evaluation"]
            report += "## Analysis Quality Metrics\n\n"
            report += f"- **Total Insights Generated:** {eval_data.get('total_insights', 0)}\n"
            report += f"- **Validated Insights:** {eval_data.get('validated_count', 0)}\n"
            report += f"- **Quality Score:** {eval_data.get('overall_quality', 0):.2f}/1.00\n"
            report += f"- **Evaluation Status:** {'✅ Passed' if eval_data.get('pass_threshold', False) else '⚠️ Needs Review'}\n\n"
        
        report += "---\n\n"
        report += "*This report was generated by the Kasparro Agentic FB Analyst system.*\n"
        
        return report
