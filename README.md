# Kasparro Agentic FB Analyst

A self-directed multi-agent system that autonomously diagnoses Facebook Ads performance, identifies ROAS fluctuation drivers, and recommends new creative directions using quantitative signals and creative messaging data.

## 🚀 Quick Start

```bash
# 1. Setup Python environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Unix

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install and start Ollama (if not already installed)
# Download from: https://ollama.ai
ollama pull mistral

# 4. Ensure data file is in project root
# synthetic_fb_ads_undergarments.csv should be in the root directory

# 5. Run analysis
python run.py "Analyze ROAS drop in last 7 days"
```

## 📊 Data Setup

Place `synthetic_fb_ads_undergarments.csv` in the project root directory. The dataset should contain:
- Campaign structure: `campaign_name`, `adset_name`
- Metrics: `spend`, `impressions`, `clicks`, `ctr`, `purchases`, `revenue`, `roas`
- Dimensions: `creative_type`, `creative_message`, `audience_type`, `platform`, `country`
- Time: `date` column

**Sample mode:** To test with a smaller dataset, edit `config/config.yaml`:
```yaml
data:
  use_sample: true
  sample_size: 1000
```

## 🏗️ Architecture

### Agent Flow

```
┌──────────────┐
│  User Query  │
└──────┬───────┘
       │
       v
┌──────────────────────────────────────────────────────────────┐
│                    PLANNER AGENT                             │
│  • Decomposes query into structured subtasks                 │
│  • Returns: JSON list of analysis tasks                      │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           v
┌──────────────────────────────────────────────────────────────┐
│                     DATA AGENT                               │
│  • Loads CSV dataset (pandas)                                │
│  • Executes each subtask (trend analysis, segmentation, etc) │
│  • Returns: Quantitative analysis results                    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           v
┌──────────────────────────────────────────────────────────────┐
│                   INSIGHT AGENT                              │
│  • Generates hypotheses explaining performance patterns      │
│  • Uses LLM with Think → Analyze → Conclude structure        │
│  • Returns: insights.json with confidence scores             │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           v
┌──────────────────────────────────────────────────────────────┐
│                  EVALUATOR AGENT                             │
│  • Validates insights quantitatively                         │
│  • Checks: evidence count, confidence threshold, grounding   │
│  • Triggers retry if quality too low                         │
│  • Returns: validation report + filtered insights            │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           v
┌──────────────────────────────────────────────────────────────┐
│              CREATIVE GENERATOR AGENT                        │
│  • Analyzes top/bottom performing creatives                  │
│  • Generates new message variations for low-CTR campaigns    │
│  • Returns: creatives.json with testing recommendations      │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           v
                   ┌───────────────┐
                   │   OUTPUTS     │
                   ├───────────────┤
                   │ insights.json │
                   │creatives.json │
                   │  report.md    │
                   │   logs/*.jsonl│
                   └───────────────┘
```

### Agent Descriptions

| Agent | Responsibility | Input | Output |
|-------|---------------|-------|--------|
| **Planner** | Decompose user query into structured subtasks | User query + data summary | List of subtasks (JSON) |
| **Data Agent** | Execute analytical queries on dataset | Subtask definitions | Analysis results (metrics, segments, trends) |
| **Insight Agent** | Generate hypotheses explaining patterns | Analysis results + context | Insights with confidence scores |
| **Evaluator** | Validate insights quantitatively | Insights + raw data | Validation report + filtered insights |
| **Creative Generator** | Produce creative recommendations | Underperformer data + top performers | Creative variations with rationale |

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.10 | Core implementation |
| **Data Processing** | pandas, numpy | CSV loading, aggregations, calculations |
| **LLM** | Ollama (mistral:7b) | Local, free LLM inference |
| **Config** | PyYAML | Configuration management |
| **Testing** | pytest | Unit tests for evaluator |
| **Logging** | Python logging + rich | Execution traceability |

## 📂 Project Structure

```
kasparro-agentic-fb-analyst/
├── config/
│   └── config.yaml          # All configuration (LLM, thresholds, paths)
├── src/
│   ├── agents/
│   │   ├── planner.py        # Query decomposition
│   │   ├── data_agent.py     # Data analysis execution
│   │   ├── insight_agent.py  # Hypothesis generation
│   │   ├── evaluator.py      # Validation & confidence scoring
│   │   └── creative_gen.py   # Creative recommendations
│   ├── utils/
│   │   ├── llm.py           # Ollama/OpenAI client wrapper
│   │   ├── data_loader.py   # CSV loading & preprocessing
│   │   └── config.py        # Config loader
│   └── orchestrator.py      # Main agent coordination
├── tests/
│   └── test_evaluator.py    # Evaluator unit tests
├── reports/                 # Generated outputs (gitignored)
│   ├── insights.json
│   ├── creatives.json
│   └── report.md
├── logs/                    # Execution logs (gitignored)
│   └── execution.jsonl
├── synthetic_fb_ads_undergarments.csv  # Dataset
├── requirements.txt
├── run.py                   # CLI entry point
├── Makefile                # Setup & run commands
└── README.md
```

## 🎯 Usage Examples

### Basic Analysis
```bash
python run.py "Analyze ROAS drop in last 7 days"
```

### Creative Performance
```bash
python run.py "Why is CTR declining for retargeting campaigns?"
```

### Segment Comparison
```bash
python run.py "Compare performance across creative types and platforms"
```

## 📤 Outputs

### 1. `reports/insights.json`
Structured insights with confidence scores:
```json
[
  {
    "id": "insight_1",
    "category": "roas_decline",
    "hypothesis": "ROAS declined 23% due to audience fatigue",
    "evidence": ["CTR dropped 18%", "Frequency up 40%"],
    "confidence": 0.75,
    "reasoning": "Correlation between frequency and CTR decline",
    "recommendation": "Refresh creative or expand to LAL audiences"
  }
]
```

### 2. `reports/creatives.json`
Creative recommendations for low-CTR campaigns:
```json
[
  {
    "campaign": "Men ComfortMax Launch",
    "current_issue": "Generic messaging, CTR 0.8%",
    "creative_variations": [
      {
        "variation_id": "var_1",
        "creative_type": "UGC",
        "headline": "Finally, boxers that don't ride up",
        "message": "Tested by 10,000+ men. Zero complaints.",
        "cta": "Try Risk-Free",
        "rationale": "Addresses pain point with social proof"
      }
    ]
  }
]
```

### 3. `reports/report.md`
Human-readable markdown report with executive summary, detailed insights, and creative recommendations.

### 4. `logs/execution.jsonl`
JSON Lines format execution log for full traceability.

## 📋 Sample Output

See the **`samples/`** folder for real output examples from the query *"Why is ROAS declining?"*:

- **[samples/insights.json](samples/insights.json)** - 2 validated insights with confidence scores (0.85, 0.75)
- **[samples/creatives.json](samples/creatives.json)** - 3 creative recommendations for underperforming campaigns
- **[samples/report.md](samples/report.md)** - Full markdown report with executive summary
- **[samples/execution.jsonl](samples/execution.jsonl)** - Complete execution trace with timing data

These outputs were generated in **~7 seconds** using Groq API (llama-3.3-70b-versatile).

## ⚙️ Configuration

Edit `config/config.yaml` to customize:

```yaml
# LLM settings
llm:
  provider: "ollama"  # or "openai"
  model: "mistral"    # or "llama3.1", "gpt-4o"
  temperature: 0.7

# Analysis thresholds
thresholds:
  confidence_min: 0.6        # Min confidence for insights
  roas_change_threshold: 0.15
  ctr_low_threshold: 0.01

# Data settings
data:
  csv_path: "synthetic_fb_ads_undergarments.csv"
  use_sample: false
  sample_size: 1000
```

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_evaluator.py::test_evaluate_valid_insight -v
```

## 🔍 Validation Logic

The **Evaluator Agent** performs these checks:
1. ✅ **Completeness**: Hypothesis, evidence (≥2 items), confidence, reasoning, recommendation
2. ✅ **Confidence Range**: 0.0 ≤ confidence ≤ 1.0
3. ✅ **Threshold**: confidence ≥ 0.6 (configurable)
4. ✅ **Quantitative Evidence**: At least one piece of evidence includes numbers
5. ✅ **Numerical Grounding**: Claims in hypothesis match data (±10% tolerance)

If quality is too low (< 2 insights or overall quality < 0.5), the system automatically retries insight generation.

## 🎨 Prompt Design Principles

All prompts follow this structure:

1. **System Prompt**: Role definition, output format (JSON schema), rules
2. **User Prompt**: Context + data summary + specific task
3. **Reasoning Structure**: Think → Analyze → Conclude
4. **Format Enforcement**: "Output ONLY valid JSON" to prevent hallucination
5. **Reflection**: Retry logic for low-confidence results

See `src/agents/*.py` for full prompt implementations.

## 📈 Observability

- **Structured Logs**: `logs/execution.jsonl` contains timestamped steps with full data
- **Evaluation Metadata**: Each insight includes validation checks and quality scores
- **Execution Log**: Full agent pipeline trace in final results

## 🚢 Deployment Notes

### Requirements
- Python 3.10+
- Ollama installed and running (`ollama serve`)
- Model downloaded: `ollama pull mistral`
- ~4GB RAM for model inference

### Performance
- Average query execution: 30-60 seconds
- Insight generation: 2 attempts max (with retry)
- Creative generation: 3-5 recommendations per run

## 🤝 Contributing

This is an assignment submission project. For evaluation purposes:

- **Git Hygiene**: 3+ meaningful commits
- **Release Tag**: `v1.0` on final version
- **Self-Review PR**: Describes design choices and tradeoffs

## 📝 License

MIT License - Built for Kasparro Applied AI Engineer Assignment

## 🙋 Contact

For questions about this submission, please refer to the assignment submission form.

---

**Built with:** Python 3.10 | pandas | Ollama (Mistral) | Pure multi-agent orchestration (no frameworks)
