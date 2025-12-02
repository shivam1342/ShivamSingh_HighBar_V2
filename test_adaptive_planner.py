"""
Test script for Adaptive Planner functionality
"""
import yaml
import pandas as pd
import numpy as np
from src.agents.planner import PlannerAgent
from src.utils.llm import LLMClient

# Load config
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Mock LLM client for testing
class MockLLMClient:
    def __init__(self, config):
        self.model = config.get("model", "mock")
    
    def generate(self, prompt, system_prompt=None):
        # Return mock plan with thresholds from prompt
        return """{
            "subtasks": [
                {
                    "task_id": "1",
                    "task_type": "identify_underperformers",
                    "description": "Find low CTR campaigns",
                    "parameters": {"metric": "ctr", "threshold": 0.007}
                }
            ]
        }"""

# Create planner with mock LLM
llm_client = MockLLMClient(config["llm"])
planner = PlannerAgent(llm_client, config)

print("="*80)
print("ADAPTIVE PLANNER TEST")
print("="*80)

# Test 1: High variance data
print("\n[TEST 1] HIGH VARIANCE DATA (volatile campaigns)")
print("-"*80)

# Create high variance dataset
np.random.seed(42)
high_var_data = pd.DataFrame({
    'campaign_id': [f'C{i}' for i in range(20)],
    'ctr': np.random.uniform(0.001, 0.15, 20),  # Large spread
    'roas': np.random.uniform(0.2, 8.0, 20),    # Very volatile
    'cvr': np.random.uniform(0.005, 0.12, 20)
})

# Calculate actual CV
ctr_cv = high_var_data['ctr'].std() / high_var_data['ctr'].mean()
roas_cv = high_var_data['roas'].std() / high_var_data['roas'].mean()

print(f"Dataset stats:")
print(f"  CTR CV: {ctr_cv:.3f}")
print(f"  ROAS CV: {roas_cv:.3f}")
print(f"  Sample size: {len(high_var_data)}")

data_summary = {
    "date_range": {"start": "2024-01-01", "end": "2024-01-31", "days": 31},
    "campaigns": {"count": 20},
    "metrics": {
        "total_spend": 10000,
        "avg_roas": high_var_data['roas'].mean(),
        "avg_ctr": high_var_data['ctr'].mean()
    },
    "dimensions": {
        "creative_types": {"Image": 10, "Video": 10},
        "platforms": {"Facebook": 15, "Instagram": 5},
        "countries": {"US": 20}
    }
}

# Assess quality and adapt
quality = planner._assess_data_quality(high_var_data, data_summary)
thresholds = planner._adapt_thresholds(quality)

print(f"\nData Quality Assessment:")
print(f"  Variance Level: {quality['variance_level']}")
print(f"  Quality Level: {quality['quality_level']}")
print(f"  CV Values: {quality['cv_values']}")

print(f"\nAdaptive Thresholds:")
print(f"  CTR Threshold: {thresholds['ctr_threshold']:.4f} (default: {planner.default_underperformer_threshold:.4f})")
print(f"  CVR Threshold: {thresholds['cvr_threshold']:.4f}")
print(f"  ROAS Threshold: {thresholds['roas_threshold']:.2f} (default: {planner.default_roas_threshold:.2f})")

expected_multiplier = config["thresholds"]["planner"]["adaptive"]["high_variance_multiplier"]
print(f"\n✓ Expected: Thresholds LOWERED by {(1-expected_multiplier)*100:.0f}% due to high variance")

# Test 2: Low variance data
print("\n" + "="*80)
print("[TEST 2] LOW VARIANCE DATA (stable campaigns)")
print("-"*80)

# Create low variance dataset
low_var_data = pd.DataFrame({
    'campaign_id': [f'C{i}' for i in range(60)],
    'ctr': np.random.uniform(0.025, 0.035, 60),  # Tight range
    'roas': np.random.uniform(2.8, 3.2, 60),     # Very stable
    'cvr': np.random.uniform(0.02, 0.025, 60)
})

# Calculate actual CV
ctr_cv = low_var_data['ctr'].std() / low_var_data['ctr'].mean()
roas_cv = low_var_data['roas'].std() / low_var_data['roas'].mean()

print(f"Dataset stats:")
print(f"  CTR CV: {ctr_cv:.3f}")
print(f"  ROAS CV: {roas_cv:.3f}")
print(f"  Sample size: {len(low_var_data)}")

data_summary["campaigns"]["count"] = 60
data_summary["metrics"]["avg_roas"] = low_var_data['roas'].mean()
data_summary["metrics"]["avg_ctr"] = low_var_data['ctr'].mean()

# Assess quality and adapt
quality = planner._assess_data_quality(low_var_data, data_summary)
thresholds = planner._adapt_thresholds(quality)

print(f"\nData Quality Assessment:")
print(f"  Variance Level: {quality['variance_level']}")
print(f"  Quality Level: {quality['quality_level']}")
print(f"  CV Values: {quality['cv_values']}")

print(f"\nAdaptive Thresholds:")
print(f"  CTR Threshold: {thresholds['ctr_threshold']:.4f} (default: {planner.default_underperformer_threshold:.4f})")
print(f"  CVR Threshold: {thresholds['cvr_threshold']:.4f}")
print(f"  ROAS Threshold: {thresholds['roas_threshold']:.2f} (default: {planner.default_roas_threshold:.2f})")

expected_multiplier = config["thresholds"]["planner"]["adaptive"]["low_variance_multiplier"]
print(f"\n✓ Expected: Thresholds RAISED by {(expected_multiplier-1)*100:.0f}% due to low variance")

# Test 3: Medium variance (default behavior)
print("\n" + "="*80)
print("[TEST 3] MEDIUM VARIANCE DATA (normal campaigns)")
print("-"*80)

medium_var_data = pd.DataFrame({
    'campaign_id': [f'C{i}' for i in range(30)],
    'ctr': np.random.uniform(0.01, 0.05, 30),
    'roas': np.random.uniform(1.5, 3.5, 30),
    'cvr': np.random.uniform(0.01, 0.04, 30)
})

ctr_cv = medium_var_data['ctr'].std() / medium_var_data['ctr'].mean()

print(f"Dataset stats:")
print(f"  CTR CV: {ctr_cv:.3f}")
print(f"  Sample size: {len(medium_var_data)}")

data_summary["campaigns"]["count"] = 30
data_summary["metrics"]["avg_roas"] = medium_var_data['roas'].mean()

quality = planner._assess_data_quality(medium_var_data, data_summary)
thresholds = planner._adapt_thresholds(quality)

print(f"\nData Quality Assessment:")
print(f"  Variance Level: {quality['variance_level']}")
print(f"  Quality Level: {quality['quality_level']}")

print(f"\nAdaptive Thresholds:")
print(f"  CTR Threshold: {thresholds['ctr_threshold']:.4f} (default: {planner.default_underperformer_threshold:.4f})")
print(f"  ROAS Threshold: {thresholds['roas_threshold']:.2f} (default: {planner.default_roas_threshold:.2f})")

print(f"\n✓ Expected: Thresholds UNCHANGED (using defaults)")

print("\n" + "="*80)
print("✅ ADAPTIVE PLANNER TEST COMPLETE")
print("="*80)
print("\nSummary:")
print("1. High variance → Lower thresholds (more lenient)")
print("2. Low variance → Raise thresholds (more strict)")
print("3. Medium variance → Default thresholds")
print("4. All thresholds loaded from config.yaml (no hardcoding)")
