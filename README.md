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

# 3. Set up Groq API key (FREE - get from https://console.groq.com/keys)
export LLM_API_KEY="your-groq-api-key"  # Unix
# $env:LLM_API_KEY="your-groq-api-key"  # Windows PowerShell

# 4. Ensure data file is in project root
# synthetic_fb_ads_undergarments.csv should be in the root directory

# 5. Run analysis
python run.py "Which campaigns are spending the most but generating low ROAS?"
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
|-----------|-----------|---------|-------|
| **Language** | Python 3.11 | Core implementation |
| **Data Processing** | pandas, numpy | CSV loading, aggregations, calculations |
| **LLM** | Groq API (llama-3.3-70b-versatile) | Fast, free LLM inference (⚡ 10x faster than local) |
| **Config** | PyYAML | Configuration management |
| **Validation** | Schema validator | Schema drift detection, data quality checks |
| **Error Handling** | Custom exceptions | 8 categorized exception types for robust recovery |
| **Retry Logic** | Exponential backoff + jitter | Automatic retry for LLM failures with smart delays |
| **Logging** | Structured JSONL | Full observability with timestamped event logs |
| **Testing** | pytest | Unit tests for evaluator |

## 🛡️ Production Features (P0 Requirements)

### 1. Exponential Backoff Retry with Jitter
- **Automatic retry** on LLM API failures (rate limits, timeouts, network errors)
- **Smart delays**: 1s → 2s → 4s → 8s with randomized jitter to prevent thundering herd
- **Configurable**: max retries, base delay, retriable exceptions
- **Decorator-based**: `@exponential_backoff_with_jitter` applies to all LLM calls

```python
# Example: Automatic retry on Groq API failures
@exponential_backoff_with_jitter(max_retries=3, base_delay=1.0)
def generate(self, prompt, system_prompt):
    # LLM call with automatic retry
    response = requests.post(...)
```

### 2. Categorized Exception Hierarchy
8 specialized exception types for precise error handling:
- **LLMAPIError**: Rate limits, auth failures, model errors (recoverable)
- **DataValidationError**: Missing columns, invalid data (non-recoverable)
- **SchemaError**: Schema mismatches, drift detection (non-recoverable)
- **JSONParseError**: LLM response parsing failures (recoverable)
- **TimeoutError**: Request timeouts (recoverable)
- **InsufficientDataError**: Not enough data for analysis (non-recoverable)
- **EvaluationFailedError**: Quality checks failed after max retries (non-recoverable)
- **AgentException**: Base class with recoverable flag

```python
# Exception handling example
try:
    insights = insight_agent.generate_insights(...)
except JSONParseError as e:
    logger.error(f"LLM returned invalid JSON: {e.raw_response[:200]}")
    # Automatic fallback to default insights
except DataValidationError as e:
    logger.error(f"Data quality issue: {e.missing_columns}")
    # Non-recoverable - stop execution
```

### 3. Schema Validation & Drift Detection
- **Validates data** against expected schema before processing
- **Detects drift**: New columns, removed columns, type mismatches
- **Fuzzy matching**: Suggests renamed columns ("Did you mean 'spend' instead of 'cost'?")
- **Auto-documentation**: Saves detected schema snapshots for debugging
- **Quality checks**: Missing value %, row count, date range validation

```yaml
# config/schemas/schema_v1.yaml defines expected structure
required_columns:
  spend:
    type: float64
    min_value: 0
  revenue:
    type: float64
    min_value: 0
  # Detects if new column 'campaign_name_clean' appears (drift!)
```

### 4. Structured JSONL Logging
- **Complete observability**: Every agent start/complete/error logged
- **LLM call tracking**: Prompts, responses, latency, token usage
- **Performance metrics**: Duration for each agent, quality scores
- **Retry visibility**: Logs each retry attempt with reason and delay
- **JSON Lines format**: Easy parsing for analysis dashboards

```jsonl
{"timestamp": "2025-12-02T00:15:23", "agent": "planner", "event": "start"}
{"timestamp": "2025-12-02T00:15:24", "agent": "planner", "event": "llm_call", "duration_seconds": 0.89}
{"timestamp": "2025-12-02T00:15:24", "agent": "planner", "event": "complete", "duration_seconds": 0.91}
```

### 5. Query-Adaptive Intelligence
- **Insights focus on user question**: InsightAgent receives user_query to generate relevant insights
- **Creatives implement insights**: CreativeGenerator receives validated insights and builds on them
- **No repetition**: Prompts emphasize "implement insights, don't repeat them"
- **Example**: Query "Which audiences perform better?" → Insights about audience saturation → Creatives targeting specific audiences

**Before (v1)**: Generic insights + creatives that repeated recommendations  
**After (v2)**: Query-specific insights + actionable creative variations

### 6. Metric Validation & Aliasing
- **Validates metrics** before use (prevents KeyError crashes)
- **Alias mapping**: "sales" → "revenue", "conversions" → "purchases"
- **Smart fallbacks**: Invalid metric → falls back to default (CTR) with warning
- **Planner guidance**: System prompt lists exact available metrics

```python
# Handles user queries like "campaigns with zero sales"
METRIC_ALIASES = {'sales': 'revenue', 'conversions': 'purchases'}
# Automatically maps 'sales' → 'revenue' before querying data
```

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

### Query Adaptation Examples

**Query 1**: *"Should I increase budget on Instagram or Facebook?"*
- ✅ **Insight**: "Facebook outperforms Instagram (ROAS 5.97 vs 5.68)"
- ✅ **Creative**: Platform-specific ad variations for both channels

**Query 2**: *"Which audience types are performing better?"*
- ✅ **Insight**: "Retargeting ROAS 9.33 vs Lookalike 5.76 vs Broad 5.00"
- ✅ **Creative**: "Men's Undergarments Retargeting" + "Women's Lookalike" campaigns

**Query 3**: *"Which campaigns are spending the most but generating zero sales?"*
- ✅ **Metric validation**: Automatically maps "sales" → "revenue"
- ✅ **Insight**: Identifies high-spend, low-revenue campaigns
- ✅ **Creative**: Fresh angles to revive underperforming campaigns

## ⚙️ Configuration

Edit `config/config.yaml` to customize:

```yaml
# LLM Configuration - Groq API (FREE, FAST)
llm:
  model: "llama-3.3-70b-versatile"
  api_key: ""  # Or set LLM_API_KEY environment variable (recommended)
  temperature: 0.5  # 0=focused, 1=creative
  max_tokens: 1500
  timeout: 60  # Request timeout in seconds

# Analysis thresholds
thresholds:
  confidence_min: 0.6        # Min confidence for insights
  roas_change_threshold: 0.15
  ctr_low_threshold: 0.01
  min_spend_for_analysis: 100

# Data settings
data:
  csv_path: "synthetic_fb_ads_undergarments.csv"
  use_sample: false
  sample_size: 1000

# Output paths
outputs:
  reports_dir: "reports"
  logs_dir: "logs"
  insights_file: "reports/insights.json"
  creatives_file: "reports/creatives.json"
  report_file: "reports/report.md"

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  format: "json"
  file: "logs/execution.jsonl"
```

**Why Groq?**
- ⚡ **10x faster** than local Ollama (0.8s vs 8s per LLM call)
- 🆓 **Free tier**: Generous rate limits for development
- 🚀 **Production-ready**: Reliable API with automatic retries
- 📊 **Latest models**: llama-3.3-70b-versatile (Dec 2024)

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
- Groq API key (free from https://console.groq.com/keys)
- Set `LLM_API_KEY` environment variable
- Minimal RAM (~500MB for pandas data processing)

### Performance

**v2 (Current - Groq API with P0 features):**
- ⚡ **Average query execution**: 6-9 seconds (full pipeline)
- 🎯 **LLM call latency**: 0.8-1.2s per call (Groq)
- 🔄 **Retry overhead**: +2-4s only on failures (rare with Groq's reliability)
- 📊 **Insight generation**: 2 attempts max (auto-retry on low quality)
- 🎨 **Creative generation**: 2-3 campaigns with 3 variations each
- 📝 **Structured logging**: ~60 events per execution logged to JSONL

**v1 (Previous - Ollama local):**
- 🐌 **Average query execution**: 30-60 seconds
- ⏳ **LLM call latency**: 8-12s per call (local inference)
- ⚠️ **No retry logic**: Single attempt, manual restart on failure
- 📉 **No structured logging**: Basic console logs only

**Performance Comparison:**
```
Metric                  | v1 (Ollama)  | v2 (Groq)   | Improvement
------------------------|--------------|-------------|-------------
Total execution time    | 30-60s       | 6-9s        | 5-7x faster
LLM call latency        | 8-12s        | 0.8-1.2s    | 10x faster
Error recovery          | Manual       | Automatic   | ✅ Robust
Observability          | Basic logs   | JSONL events| ✅ Production-ready
Query adaptation       | Generic      | User-focused| ✅ Relevant
Metric validation      | None         | Full        | ✅ No crashes
```

### Production Readiness
✅ **Error handling**: 8 exception types with retry logic  
✅ **Schema validation**: Detects drift, suggests fixes  
✅ **Structured logging**: Full observability in JSONL  
✅ **Query adaptation**: Insights answer user's actual question  
✅ **Metric validation**: Prevents crashes from invalid metrics  
✅ **Automatic retry**: Recovers from transient LLM failures

## 🤝 Contributing

This is an assignment submission project. For evaluation purposes:

- **Git Hygiene**: 3+ meaningful commits
- **Release Tag**: `v1.0` on final version
- **Self-Review PR**: Describes design choices and tradeoffs

## 📝 License

MIT License - Built for Kasparro Applied AI Engineer Assignment

---

**Built with:** Python 3.11 | pandas | Groq API (llama-3.3-70b-versatile) | Pure multi-agent orchestration (no frameworks)

**v2 Improvements:** Exponential backoff retry | 8 exception types | Schema validation | Structured JSONL logging | Query adaptation | Metric validation
