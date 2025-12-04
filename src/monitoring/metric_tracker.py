"""
MetricTracker: Stores and retrieves historical metric baselines.

This module provides functionality to:
1. Calculate statistical baselines from historical data
2. Save/load baselines to/from JSON
3. Track metrics over time for drift detection
"""

import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class MetricTracker:
    """
    Tracks metric baselines over time.
    
    Stores historical statistics (mean, std, percentiles) for key metrics
    like ROAS, CTR, CVR to enable drift detection.
    """
    
    def __init__(self, baseline_path: str = "config/baseline_metrics.json"):
        """
        Initialize MetricTracker.
        
        Args:
            baseline_path: Path to store/load baseline metrics JSON
        """
        self.baseline_path = Path(baseline_path)
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
    
    def calculate_baseline(self, df: pd.DataFrame) -> Dict:
        """
        Calculate statistical baseline from DataFrame.
        
        Computes mean, std, median, percentiles for key metrics:
        - roas: Return on Ad Spend
        - ctr: Click-Through Rate
        - cvr: Conversion Rate
        - spend: Campaign spend
        
        Args:
            df: DataFrame with metric columns
        
        Returns:
            Dictionary with baseline statistics and metadata
        """
        metrics_to_track = ['roas', 'ctr', 'cvr', 'spend']
        baseline = {}
        
        for metric in metrics_to_track:
            if metric not in df.columns:
                logger.debug(f"Metric '{metric}' not found in DataFrame, skipping")
                continue
            
            # Calculate comprehensive statistics
            baseline[metric] = {
                'mean': float(df[metric].mean()),
                'std': float(df[metric].std()),
                'median': float(df[metric].median()),
                'p25': float(df[metric].quantile(0.25)),
                'p75': float(df[metric].quantile(0.75)),
                'min': float(df[metric].min()),
                'max': float(df[metric].max()),
                'count': int(df[metric].count())
            }
        
        # Add metadata
        result = {
            'created_at': datetime.now().isoformat(),
            'data_window': {
                'start_date': df['date'].min().isoformat() if 'date' in df.columns else None,
                'end_date': df['date'].max().isoformat() if 'date' in df.columns else None,
                'total_rows': len(df)
            },
            'metrics': baseline
        }
        
        logger.info(f"Calculated baseline for {len(baseline)} metrics from {len(df)} rows")
        return result
    
    def save_baseline(self, baseline: Dict) -> None:
        """
        Save baseline to JSON file.
        
        Args:
            baseline: Baseline dictionary from calculate_baseline()
        """
        try:
            with open(self.baseline_path, 'w') as f:
                json.dump(baseline, f, indent=2)
            logger.info(f"✅ Baseline saved to {self.baseline_path}")
        except Exception as e:
            logger.error(f"Failed to save baseline: {e}")
            raise
    
    def load_baseline(self) -> Optional[Dict]:
        """
        Load previously saved baseline from JSON.
        
        Returns:
            Baseline dictionary, or None if file doesn't exist
        """
        if not self.baseline_path.exists():
            logger.debug(f"No baseline found at {self.baseline_path}")
            return None
        
        try:
            with open(self.baseline_path, 'r') as f:
                baseline = json.load(f)
            
            created_at = baseline.get('created_at', 'unknown')
            num_metrics = len(baseline.get('metrics', {}))
            logger.info(f"Loaded baseline from {created_at} with {num_metrics} metrics")
            
            return baseline
        except Exception as e:
            logger.error(f"Failed to load baseline: {e}")
            return None
    
    def update_baseline(self, df: pd.DataFrame) -> Dict:
        """
        Calculate and save new baseline, replacing the old one.
        
        Use this when drift is expected (e.g., seasonal changes, 
        business model changes) and you want to reset the baseline.
        
        Args:
            df: DataFrame with current data
        
        Returns:
            New baseline dictionary
        """
        logger.info("Updating baseline with current data...")
        baseline = self.calculate_baseline(df)
        self.save_baseline(baseline)
        logger.info("✅ Baseline updated successfully")
        return baseline
    
    def get_baseline_age_days(self) -> Optional[float]:
        """
        Get age of current baseline in days.
        
        Returns:
            Number of days since baseline was created, or None if no baseline
        """
        baseline = self.load_baseline()
        if not baseline or 'created_at' not in baseline:
            return None
        
        created_at = datetime.fromisoformat(baseline['created_at'])
        age = (datetime.now() - created_at).total_seconds() / 86400
        return age
