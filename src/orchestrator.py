"""
Orchestrator - Main agent coordination logic

REFACTORED: Now uses declarative PipelineEngine instead of procedural code.
Pipeline configuration in config/pipeline.yaml defines all stages, inputs, outputs.
Reduced from 250 → 80 lines (~68% less code).
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
from src.monitoring.alert_manager import AlertManager
from src.monitoring.health_checker import HealthChecker
from src.pipeline import PipelineEngine

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Coordinates the multi-agent workflow using declarative PipelineEngine.
    
    Pipeline stages (defined in config/pipeline.yaml):
    1. data_summary - Get dataset overview
    2. planning - Create execution plan with data quality assessment
    3. data_analysis - Execute data queries
    4. context_preparation - Prepare context for insights
    5. insight_generation - Generate hypotheses (with retry)
    6. evaluation - Validate insights (triggers retry if needed)
    7. creative_preparation - Prepare creative inputs
    8. creative_generation - Generate recommendations
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = StructuredLogger()
        
        # Initialize alert manager
        self.alert_manager = AlertManager(config)
        
        # Initialize LLM client
        self.llm_client = LLMClient(config["llm"])
        
        # Initialize data loader
        data_config = config["data"]
        self.data_loader = DataLoader(
            csv_path=data_config["csv_path"],
            use_sample=data_config.get("use_sample", False),
            sample_size=data_config.get("sample_size", 1000)
        )
        
        # Initialize agents (pass structured logger, config, and alert_manager)
        self.planner = PlannerAgent(self.llm_client, config, self.logger)
        self.data_agent = DataAgent(self.data_loader, self.config, self.logger)
        self.insight_agent = InsightAgent(self.llm_client, self.logger, self.alert_manager, config)
        self.evaluator = EvaluatorAgent(config, self.logger, self.alert_manager)
        self.creative_gen = CreativeGeneratorAgent(self.llm_client, self.logger)
        
        # Initialize health checker
        self.health_checker = HealthChecker(config, self.alert_manager)
        
        # Initialize data agent
        self.data_agent.initialize()
        
        # Initialize pipeline engine
        self.engine = PipelineEngine()
        
    def run(self, user_query: str) -> Dict[str, Any]:
        """
        Execute the full agent pipeline using PipelineEngine.
        
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
            
            # Prepare initial context
            raw_data = self.data_loader.df
            data_summary = self.data_loader.get_summary()
            
            # Run health checks before pipeline execution
            logger.info("🏥 Running pre-flight health checks...")
            health_passed = self.health_checker.run_all_checks(raw_data, data_summary)
            
            if not health_passed:
                logger.error(f"❌ Critical health check failures detected! Pipeline may produce unreliable results.")
            else:
                logger.info(f"✅ Health checks passed")
            
            context = {
                'user_query': user_query,
                'raw_data': raw_data,
                'data_summary': data_summary
            }
            
            # Prepare agents dict for engine
            agents = {
                'data_loader': self.data_loader,
                'planner': self.planner,
                'data': self.data_agent,
                'insight': self.insight_agent,
                'evaluator': self.evaluator,
                'creative': self.creative_gen
            }
            
            # Execute pipeline (engine handles all stages, timing, retries, validation)
            pipeline_output = self.engine.execute(context, agents)
            
            # Extract final results
            insights = pipeline_output.get('insights', [])
            evaluation = pipeline_output.get('evaluation', {})
            creatives = pipeline_output.get('creatives', [])
            
            # Build results dict (for backward compatibility)
            results = {
                "query": user_query,
                "execution_time": datetime.now().isoformat(),
                "plan": self.engine.stage_outputs.get('planning', []),
                "analysis_results": self.engine.stage_outputs.get('data_analysis', []),
                "insights": insights,
                "evaluation": evaluation,
                "creative_recommendations": creatives,
                "stage_timings": pipeline_output.get('stage_timings', {}),
                "retry_counts": pipeline_output.get('retry_counts', {})
            }
            
            # Log orchestration completion
            pipeline_duration = time.time() - pipeline_start
            self.logger.log_agent_complete(
                "orchestrator",
                output_data={
                    "insight_count": len(insights),
                    "creative_count": len(creatives),
                    "quality_score": evaluation.get("overall_quality", 0),
                    "passed_validation": evaluation.get("pass_threshold", False)
                },
                duration_seconds=pipeline_duration
            )
            
            # Log all alerts if any were raised
            if self.alert_manager.get_alerts():
                logger.info("\n" + "="*80)
                self.alert_manager.log_all_alerts()
                logger.info("="*80 + "\n")
            
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
