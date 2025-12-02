# 🎯 What's NEW in P1 - Adaptive Planner

## **Before Running (v2.0 vs P1 Comparison)**

### **What You'll See in Terminal Logs:**

#### **OLD (v2.0):**
```
2025-12-03 00:32:29,962 - src.agents.planner - INFO - Planning for query: Show me underperforming campaigns with low CTR
2025-12-03 00:32:30,849 - src.agents.planner - INFO - Generated plan with 4 subtasks
```
❌ No data quality assessment  
❌ No adaptive threshold logging  
❌ Always uses hardcoded 0.01

---

#### **NEW (P1 - Adaptive Planner):**
```
2025-12-03 00:32:29,962 - src.agents.planner - INFO - Planning for query: Show me underperforming campaigns with low CTR
2025-12-03 00:32:29,965 - src.agents.planner - INFO - High variance detected, lowering thresholds by 30%  ← ✅ NEW!
2025-12-03 00:32:29,965 - src.agents.planner - INFO - Data quality: volatile, Adaptive thresholds: {'ctr_threshold': 0.007, 'cvr_threshold': 0.007, 'roas_threshold': 1.43}  ← ✅ NEW!
2025-12-03 00:32:30,849 - src.agents.planner - INFO - Generated plan with 4 subtasks
```
✅ **Data quality assessed** before planning  
✅ **"High variance detected"** - automatically lowered thresholds  
✅ **Dynamic thresholds** - 0.007 instead of hardcoded 0.01  
✅ **ROAS threshold adjusted** - 1.43 instead of default 1.0

---

## **Key Changes You'll Notice:**

### **1. Log Output Shows Adaptive Behavior**

Look for these NEW log lines:
- `High variance detected, lowering thresholds by 30%` ← Volatile data
- `Low variance detected, raising thresholds by 20%` ← Stable data  
- `Medium variance, using default thresholds` ← Normal data
- `Data quality: volatile/stable/medium` ← Quality assessment
- `Adaptive thresholds: {'ctr_threshold': X}` ← Dynamic values

### **2. Different Data → Different Thresholds**

**Your synthetic data (high variance):**
- CTR CV: 0.390 (medium)
- ROAS CV: **1.708** (HIGH!)
- Result: Thresholds **LOWERED 30%** (0.01 → 0.007)

**If you had stable data (low variance):**
- CTR CV: 0.098 (low)
- ROAS CV: 0.039 (low)
- Result: Thresholds **RAISED 20%** (0.01 → 0.012)

### **3. Config-Driven (No Hardcoding)**

**Before (v2.0):**
```python
# HARDCODED in planner.py lines 156, 214
"threshold": 0.01  # ❌ Can't change without editing code
```

**After (P1):**
```yaml
# config/config.yaml
thresholds:
  planner:
    default_underperformer_threshold: 0.01  # ✅ Easy to change
    adaptive:
      high_variance_multiplier: 0.7   # ✅ Tune behavior
      low_variance_multiplier: 1.2
```

---

## **How to Test Different Scenarios:**

### **Test 1: See High Variance Behavior (Current)**
```bash
python run.py "Show me underperforming campaigns with low CTR"
```
**Expected:**
- Log: "High variance detected, lowering thresholds by 30%"
- Threshold: 0.007 (more lenient, catches more underperformers)

### **Test 2: Modify Config to See Impact**
Edit `config/config.yaml`:
```yaml
planner:
  default_underperformer_threshold: 0.02  # Change default
```
Run again:
```bash
python run.py "Show me underperforming campaigns with low CTR"
```
**Expected:**
- Threshold: 0.014 (30% lower than new default 0.02)

### **Test 3: Check Different Data Quality**
Run the test script:
```bash
python test_adaptive_planner.py
```
**Expected:**
- 3 scenarios tested: High/Low/Medium variance
- Different thresholds for each

---

## **What Changed in Code:**

### **Files Modified:**

1. **`config/config.yaml`**
   - Added `thresholds.planner` section
   - Added `adaptive` rules with multipliers
   - Added CV thresholds

2. **`src/agents/planner.py`**
   - Added `config` parameter to `__init__`
   - NEW: `_assess_data_quality()` method (calculates CV)
   - NEW: `_adapt_thresholds()` method (adjusts based on variance)
   - Modified `plan()` to accept `raw_data` parameter
   - Updated `_build_prompt()` to include adaptive thresholds
   - Removed hardcoded 0.01 from `_get_default_plan()`

3. **`src/orchestrator.py`**
   - Pass `config` to PlannerAgent init
   - Pass `raw_data` to `planner.plan()`

---

## **Why This Matters:**

### **Business Impact:**

**Scenario 1: Volatile Campaign (e.g., new product launch)**
- High variance in metrics (CV > 0.5)
- OLD: Misses underperformers with threshold 0.01
- NEW: Lower threshold (0.007) catches more candidates for optimization
- **Result:** Find issues earlier, optimize faster

**Scenario 2: Stable Campaign (e.g., mature evergreen product)**
- Low variance in metrics (CV < 0.2)
- OLD: Too many false positives with threshold 0.01
- NEW: Higher threshold (0.012) filters noise
- **Result:** Focus on real issues, less alert fatigue

**Scenario 3: Normal Campaign**
- Medium variance
- Uses default threshold (0.01)
- **Result:** Consistent with historical behavior

---

## **Technical Improvements:**

✅ **No Hardcoded Values** - All thresholds from config  
✅ **Data-Aware** - Assesses quality before planning  
✅ **Adaptive** - Different plans for different data characteristics  
✅ **Maintainable** - Easy to tune via config, no code changes  
✅ **Observable** - Logs show decision-making process  
✅ **Testable** - Can verify with different data distributions

---

## **Next Steps:**

After testing this, we'll implement:
1. **Adaptive Evaluator** - Dynamic confidence thresholds
2. **Configuration-Driven Everything** - ThresholdManager class
3. **Orchestrator Cleanup** - Declarative pipeline

---

## **Quick Verification Checklist:**

Run `python run.py "Show me underperforming campaigns with low CTR"` and check:

- [ ] Log shows "High variance detected, lowering thresholds by 30%"
- [ ] Log shows "Data quality: volatile"
- [ ] Log shows "Adaptive thresholds: {'ctr_threshold': 0.007...}"
- [ ] Threshold is 0.007, NOT 0.01
- [ ] No errors or warnings
- [ ] Report generated successfully

If all checked, **Adaptive Planner is working! ✅**
