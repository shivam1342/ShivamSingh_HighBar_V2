"""
Evaluator Agent - Validates insights and checks confidence levels
"""
import logging
import time
from typing import Dict, List, Any
import numpy as np
from src.utils.structured_logger import StructuredLogger

logger = logging.getLogger(__name__)


class EvaluatorAgent:
    """
    Validates insights with quantitative checks and confidence scoring
    """
    
    def __init__(self, config: Dict[str, Any], structured_logger: StructuredLogger = None):
        self.confidence_threshold = config.get("thresholds", {}).get("confidence_min", 0.6)
        self.min_evidence_count = 2
        self.logger = structured_logger or StructuredLogger()
        
    def evaluate_insights(
        self,
        insights: List[Dict[str, Any]],
        analysis_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate insights against data and confidence thresholds
        
        Args:
            insights: Generated insights from insight agent
            analysis_results: Raw analysis data for validation
            
        Returns:
            Evaluation report with validated insights and quality scores
        """
        # Log agent start
        self.logger.log_agent_start(
            "evaluator",
            input_data={
                "insight_count": len(insights),
                "analysis_result_count": len(analysis_results),
                "confidence_threshold": self.confidence_threshold
            }
        )
        
        start_time = time.time()
        
        try:
            logger.info(f"Evaluating {len(insights)} insights")
            
            validated_insights = []
            rejected_insights = []
            
            for insight in insights:
                validation_result = self._validate_insight(insight, analysis_results)
                
                # Log individual validation
                self.logger.log_validation(
                    validation_type=f"insight_{insight.get('category', 'unknown')}",
                    passed=validation_result["is_valid"],
                    details={
                        "insight_id": insight.get("id"),
                        "checks": validation_result.get("checks", {}),
                        "rejection_reason": validation_result.get("rejection_reason")
                    }
                )
                
                if validation_result["is_valid"]:
                    # Enhance insight with validation metadata
                    insight["validation"] = validation_result
                    validated_insights.append(insight)
                else:
                    insight["rejection_reason"] = validation_result["rejection_reason"]
                    rejected_insights.append(insight)
            
            # Calculate overall quality score
            quality_score = self._calculate_quality_score(validated_insights)
            
            # Log quality metrics
            self.logger.log_metric(
                "evaluation_quality_score",
                quality_score,
                context={
                    "validated_count": len(validated_insights),
                    "rejected_count": len(rejected_insights),
                    "pass_threshold": quality_score >= 0.7
                }
            )
            
            evaluation_report = {
                "total_insights": len(insights),
                "validated_count": len(validated_insights),
                "rejected_count": len(rejected_insights),
                "overall_quality": quality_score,
                "validated_insights": validated_insights,
                "rejected_insights": rejected_insights,
                "pass_threshold": quality_score >= 0.7
            }
            
            logger.info(
                f"Evaluation complete: {len(validated_insights)}/{len(insights)} passed "
                f"(quality score: {quality_score:.2f})"
            )
            
            # Log completion
            duration = time.time() - start_time
            self.logger.log_agent_complete(
                "evaluator",
                output_data={
                    "validated_count": len(validated_insights),
                    "rejected_count": len(rejected_insights),
                    "quality_score": quality_score,
                    "passed_threshold": quality_score >= 0.7
                },
                duration_seconds=duration
            )
            
            return evaluation_report
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            self.logger.log_agent_error(
                "evaluator",
                error=e,
                context={
                    "insight_count": len(insights),
                    "duration_before_error": duration
                }
            )
            raise
    
    def _validate_insight(
        self,
        insight: Dict[str, Any],
        analysis_results: List[Dict[str, Any]]
    ) -> Dict[str, bool]:
        """Validate a single insight"""
        
        checks = {
            "has_hypothesis": bool(insight.get("hypothesis")),
            "has_evidence": len(insight.get("evidence", [])) >= self.min_evidence_count,
            "has_confidence": "confidence" in insight,
            "confidence_in_range": 0.0 <= insight.get("confidence", 0) <= 1.0,
            "meets_threshold": insight.get("confidence", 0) >= self.confidence_threshold,
            "has_reasoning": bool(insight.get("reasoning")),
            "has_recommendation": bool(insight.get("recommendation")),
            "evidence_is_quantitative": self._check_quantitative_evidence(insight.get("evidence", []))
        }
        
        # Check if numbers in hypothesis are supported by data
        checks["numerically_grounded"] = self._check_numerical_grounding(insight, analysis_results)
        
        is_valid = all([
            checks["has_hypothesis"],
            checks["has_evidence"],
            checks["has_confidence"],
            checks["confidence_in_range"],
            checks["meets_threshold"],
            checks["has_reasoning"]
        ])
        
        rejection_reason = None
        if not is_valid:
            if not checks["meets_threshold"]:
                rejection_reason = f"Confidence {insight.get('confidence', 0):.2f} below threshold {self.confidence_threshold}"
            elif not checks["has_evidence"]:
                rejection_reason = f"Insufficient evidence (need >= {self.min_evidence_count})"
            else:
                rejection_reason = "Failed basic validation checks"
        
        return {
            "is_valid": is_valid,
            "checks": checks,
            "rejection_reason": rejection_reason,
            "quality_factors": {
                "completeness": sum(checks.values()) / len(checks),
                "confidence": insight.get("confidence", 0),
                "evidence_strength": len(insight.get("evidence", [])) / 5.0  # normalize to 0-1
            }
        }
    
    def _check_quantitative_evidence(self, evidence: List[str]) -> bool:
        """Check if evidence includes specific numbers"""
        quantitative_count = 0
        for item in evidence:
            # Look for numbers, percentages, or specific metrics
            if any(char.isdigit() for char in item):
                quantitative_count += 1
        
        return quantitative_count >= 1
    
    def _check_numerical_grounding(
        self,
        insight: Dict[str, Any],
        analysis_results: List[Dict[str, Any]]
    ) -> bool:
        """
        Verify that numerical claims in hypothesis are supported by data
        This is a simplified check - in production you'd do more rigorous validation
        """
        hypothesis = insight.get("hypothesis", "")
        
        # Extract percentages mentioned in hypothesis
        import re
        percentages = re.findall(r'(\d+)%', hypothesis)
        
        if not percentages:
            return True  # No specific claims to validate
        
        # Check if similar numbers appear in analysis results
        for result in analysis_results:
            if 'change_pct' in result:
                claimed_pct = float(percentages[0])
                actual_pct = abs(result['change_pct'])
                # Allow 10% tolerance
                if abs(claimed_pct - actual_pct) / max(actual_pct, 1) < 0.1:
                    return True
        
        return False  # Numbers not found in data
    
    def _calculate_quality_score(self, validated_insights: List[Dict[str, Any]]) -> float:
        """Calculate overall quality score for the insight set"""
        if not validated_insights:
            return 0.0
        
        scores = []
        for insight in validated_insights:
            validation = insight.get("validation", {})
            quality = validation.get("quality_factors", {})
            
            # Weighted average of quality factors
            score = (
                quality.get("completeness", 0) * 0.3 +
                quality.get("confidence", 0) * 0.5 +
                quality.get("evidence_strength", 0) * 0.2
            )
            scores.append(score)
        
        return float(np.mean(scores))
    
    def requires_retry(self, evaluation_report: Dict[str, Any]) -> bool:
        """Determine if insight generation should be retried"""
        return (
            evaluation_report["validated_count"] < 2 or
            evaluation_report["overall_quality"] < 0.5
        )
