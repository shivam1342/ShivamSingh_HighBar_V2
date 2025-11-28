"""
Tests for Evaluator Agent
"""
import pytest
from src.agents.evaluator import EvaluatorAgent


def test_evaluator_initialization():
    """Test evaluator can be initialized with config"""
    config = {"thresholds": {"confidence_min": 0.6}}
    evaluator = EvaluatorAgent(config)
    assert evaluator.confidence_threshold == 0.6
    assert evaluator.min_evidence_count == 2


def test_evaluate_valid_insight():
    """Test evaluation of a valid insight"""
    config = {"thresholds": {"confidence_min": 0.6}}
    evaluator = EvaluatorAgent(config)
    
    insights = [
        {
            "hypothesis": "ROAS declined 20% due to audience fatigue",
            "evidence": ["CTR dropped 15%", "Frequency increased 40%"],
            "confidence": 0.75,
            "reasoning": "High frequency correlates with declining CTR",
            "recommendation": "Refresh creative"
        }
    ]
    
    analysis_results = []
    
    evaluation = evaluator.evaluate_insights(insights, analysis_results)
    
    assert evaluation["validated_count"] == 1
    assert evaluation["rejected_count"] == 0
    assert len(evaluation["validated_insights"]) == 1


def test_evaluate_low_confidence_insight():
    """Test rejection of low confidence insight"""
    config = {"thresholds": {"confidence_min": 0.6}}
    evaluator = EvaluatorAgent(config)
    
    insights = [
        {
            "hypothesis": "Maybe ROAS changed",
            "evidence": ["Some data points"],
            "confidence": 0.3,  # Below threshold
            "reasoning": "Unclear",
            "recommendation": "Need more analysis"
        }
    ]
    
    analysis_results = []
    
    evaluation = evaluator.evaluate_insights(insights, analysis_results)
    
    assert evaluation["validated_count"] == 0
    assert evaluation["rejected_count"] == 1
    assert "below threshold" in evaluation["rejected_insights"][0]["rejection_reason"]


def test_evaluate_insufficient_evidence():
    """Test rejection of insight with insufficient evidence"""
    config = {"thresholds": {"confidence_min": 0.6}}
    evaluator = EvaluatorAgent(config)
    
    insights = [
        {
            "hypothesis": "Performance changed",
            "evidence": ["Only one piece of evidence"],  # Need at least 2
            "confidence": 0.8,
            "reasoning": "Not enough data",
            "recommendation": "Investigate"
        }
    ]
    
    analysis_results = []
    
    evaluation = evaluator.evaluate_insights(insights, analysis_results)
    
    assert evaluation["validated_count"] == 0
    assert evaluation["rejected_count"] == 1


def test_quality_score_calculation():
    """Test overall quality score calculation"""
    config = {"thresholds": {"confidence_min": 0.6}}
    evaluator = EvaluatorAgent(config)
    
    insights = [
        {
            "hypothesis": "ROAS declined 20%",
            "evidence": ["Evidence 1", "Evidence 2", "Evidence 3"],
            "confidence": 0.8,
            "reasoning": "Clear pattern",
            "recommendation": "Take action"
        },
        {
            "hypothesis": "CTR improved 10%",
            "evidence": ["Evidence A", "Evidence B"],
            "confidence": 0.7,
            "reasoning": "Solid data",
            "recommendation": "Scale up"
        }
    ]
    
    analysis_results = []
    
    evaluation = evaluator.evaluate_insights(insights, analysis_results)
    
    assert evaluation["overall_quality"] > 0.6
    assert evaluation["pass_threshold"] == True


def test_requires_retry():
    """Test retry logic"""
    config = {"thresholds": {"confidence_min": 0.6}}
    evaluator = EvaluatorAgent(config)
    
    # Scenario 1: Good evaluation - no retry
    good_eval = {
        "validated_count": 3,
        "overall_quality": 0.8
    }
    assert evaluator.requires_retry(good_eval) == False
    
    # Scenario 2: Too few insights - retry
    bad_eval_1 = {
        "validated_count": 1,
        "overall_quality": 0.7
    }
    assert evaluator.requires_retry(bad_eval_1) == True
    
    # Scenario 3: Low quality - retry
    bad_eval_2 = {
        "validated_count": 3,
        "overall_quality": 0.4
    }
    assert evaluator.requires_retry(bad_eval_2) == True
