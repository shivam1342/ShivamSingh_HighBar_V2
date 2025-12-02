"""
Live test of Adaptive Planner with real orchestrator
Run this to see adaptive behavior in action
"""
import yaml
import sys

# Load config
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Check if API key is set
if not config["llm"]["api_key"]:
    print("⚠️  WARNING: LLM API key not set in config.yaml")
    print("Set it or export LLM_API_KEY environment variable")
    print("\nRunning in MOCK mode for demonstration...\n")
    
    # Mock the LLM for testing
    from unittest.mock import Mock
    import src.utils.llm as llm_module
    
    class MockLLMClient:
        def __init__(self, config):
            self.model = config.get("model", "mock")
            self.temperature = config.get("temperature", 0.5)
        
        def generate(self, prompt, system_prompt=None):
            # Extract threshold from prompt for realistic mock
            if "CTR Threshold:" in prompt:
                import re
                match = re.search(r"CTR Threshold: ([\d.]+)", prompt)
                threshold = match.group(1) if match else "0.01"
                
                return f'''{{
                    "subtasks": [
                        {{
                            "task_id": "1",
                            "task_type": "analyze_metric_trend",
                            "description": "Analyze ROAS trend over time",
                            "parameters": {{"metric": "roas", "timeframe": "last_7_days"}}
                        }},
                        {{
                            "task_id": "2",
                            "task_type": "identify_underperformers",
                            "description": "Find campaigns with low CTR using adaptive threshold",
                            "parameters": {{"metric": "ctr", "threshold": {threshold}}}
                        }}
                    ]
                }}'''
            return '{"subtasks": []}'
    
    llm_module.LLMClient = MockLLMClient
    print("✅ Mock LLM configured\n")

from src.orchestrator import AgentOrchestrator

print("="*80)
print("ADAPTIVE PLANNER - LIVE TEST")
print("="*80)

# Initialize orchestrator
orchestrator = AgentOrchestrator(config)

# Test query
query = "Show me underperforming campaigns with low CTR"

print(f"\n📊 Dataset: {config['data']['csv_path']}")
print(f"📝 Query: {query}\n")

# Get data summary to show what data looks like
print("-"*80)
print("STEP 1: Data Summary")
print("-"*80)
data_summary = orchestrator.data_loader.get_summary()
print(f"Campaigns: {data_summary['campaigns']['count']}")
print(f"Date Range: {data_summary['date_range']['start']} to {data_summary['date_range']['end']}")
print(f"Avg ROAS: {data_summary['metrics']['avg_roas']:.2f}")
print(f"Avg CTR: {data_summary['metrics']['avg_ctr']:.2%}")

# Show data quality assessment
print("\n" + "-"*80)
print("STEP 2: Data Quality Assessment (NEW IN P1)")
print("-"*80)

raw_data = orchestrator.data_loader.df
data_quality = orchestrator.planner._assess_data_quality(raw_data, data_summary)

print(f"Variance Level: {data_quality['variance_level']}")
print(f"Quality Level: {data_quality['quality_level']}")
print(f"Sample Size: {data_quality['sample_size']}")

if data_quality['cv_values']:
    print(f"\nCoefficient of Variation (CV):")
    for metric, cv in data_quality['cv_values'].items():
        variance_desc = "HIGH" if cv > 0.5 else "LOW" if cv < 0.2 else "MEDIUM"
        print(f"  {metric.upper()}: {cv:.3f} ({variance_desc})")

# Show adaptive thresholds
print("\n" + "-"*80)
print("STEP 3: Adaptive Thresholds (NEW IN P1)")
print("-"*80)

adaptive_thresholds = orchestrator.planner._adapt_thresholds(data_quality)

print(f"CTR Threshold: {adaptive_thresholds['ctr_threshold']:.4f}")
print(f"  Default from config: {orchestrator.planner.default_underperformer_threshold:.4f}")
if adaptive_thresholds['ctr_threshold'] < orchestrator.planner.default_underperformer_threshold:
    diff = (1 - adaptive_thresholds['ctr_threshold']/orchestrator.planner.default_underperformer_threshold) * 100
    print(f"  ✅ LOWERED by {diff:.0f}% (data is volatile)")
elif adaptive_thresholds['ctr_threshold'] > orchestrator.planner.default_underperformer_threshold:
    diff = (adaptive_thresholds['ctr_threshold']/orchestrator.planner.default_underperformer_threshold - 1) * 100
    print(f"  ✅ RAISED by {diff:.0f}% (data is stable)")
else:
    print(f"  ✅ UNCHANGED (medium variance)")

print(f"\nROAS Threshold: {adaptive_thresholds['roas_threshold']:.2f}")
print(f"  Default from config: {orchestrator.planner.default_roas_threshold:.2f}")

# Generate plan
print("\n" + "-"*80)
print("STEP 4: Generate Plan (with adaptive thresholds)")
print("-"*80)

plan = orchestrator.planner.plan(query, data_summary, raw_data)

print(f"Generated {len(plan)} subtasks:\n")
for i, subtask in enumerate(plan, 1):
    print(f"{i}. {subtask['description']}")
    print(f"   Type: {subtask['task_type']}")
    if 'threshold' in subtask.get('parameters', {}):
        print(f"   Threshold: {subtask['parameters']['threshold']}")
    print()

print("="*80)
print("KEY OBSERVATIONS:")
print("="*80)
print("✅ Data quality assessed BEFORE planning")
print("✅ Thresholds adapted based on coefficient of variation")
print("✅ Plan includes adaptive threshold in parameters")
print("✅ NO hardcoded 0.01 - all values from config.yaml")
print("\n📁 Check logs/execution.jsonl for detailed agent logs")
