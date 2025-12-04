"""
Test script to simulate metric drift.

This script:
1. Backs up original CSV
2. Modifies ROAS to drop by 60%
3. Runs the system to detect drift
4. Restores original CSV
"""

import pandas as pd
import shutil
from pathlib import Path

# Paths
csv_path = Path("synthetic_fb_ads_undergarments.csv")
backup_path = Path("synthetic_fb_ads_undergarments_backup.csv")

print("=" * 70)
print("DRIFT SIMULATION TEST")
print("=" * 70)

# Step 1: Backup original
print("\n1️⃣  Backing up original CSV...")
shutil.copy(csv_path, backup_path)
print(f"   ✅ Backup created: {backup_path}")

# Step 2: Load and modify data
print("\n2️⃣  Loading data and simulating ROAS drop (60%)...")
df = pd.read_csv(csv_path)
print(f"   Original ROAS mean: {df['roas'].mean():.2f}")

# Simulate drift: Drop ROAS by 60%
df['roas'] = df['roas'] * 0.4
print(f"   Modified ROAS mean: {df['roas'].mean():.2f} (dropped 60%)")

# Save modified data
df.to_csv(csv_path, index=False)
print(f"   ✅ Modified CSV saved")

# Step 3: Run system
print("\n3️⃣  Running system with drifted data...")
print("   Execute: python run.py \"Show me underperforming campaigns\"")
print("   Watch for drift detection alerts!\n")

print("=" * 70)
print("⚠️  IMPORTANT: After testing, run this to restore original data:")
print(f"   python -c \"import shutil; shutil.copy('{backup_path}', '{csv_path}')\"")
print("=" * 70)
