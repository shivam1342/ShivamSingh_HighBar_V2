"""
Data loading and preprocessing utilities
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

from src.utils.schema_validator import SchemaValidator
from src.utils.exceptions import DataValidationError, SchemaError

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and preprocess Facebook Ads dataset"""
    
    def __init__(
        self, 
        csv_path: str, 
        use_sample: bool = False, 
        sample_size: int = 1000,
        schema_path: str = "config/schemas/schema_v1.yaml",
        validate_schema: bool = True
    ):
        self.csv_path = csv_path
        self.use_sample = use_sample
        self.sample_size = sample_size
        self.df: Optional[pd.DataFrame] = None
        self.validate_schema = validate_schema
        
        # Initialize schema validator
        if validate_schema:
            try:
                self.schema_validator = SchemaValidator(schema_path)
                logger.info("Schema validator initialized")
            except Exception as e:
                logger.warning(f"Schema validator initialization failed: {e}. Proceeding without validation.")
                self.validate_schema = False
        
    def load(self) -> pd.DataFrame:
        """Load CSV and perform basic preprocessing"""
        try:
            logger.info(f"Loading data from {self.csv_path}")
            self.df = pd.read_csv(self.csv_path)
            
            # Basic preprocessing
            self._preprocess()
            
            # SCHEMA VALIDATION - Check before processing
            if self.validate_schema:
                try:
                    validation_report = self.schema_validator.validate(self.df)
                    logger.info("✅ Schema validation passed")
                    
                    # Log warnings if any
                    if validation_report.get("warnings"):
                        for warning in validation_report["warnings"]:
                            logger.warning(f"Schema warning: {warning}")
                    
                    # Log drift if detected
                    if validation_report.get("drift_detected"):
                        drift = validation_report["drift_detected"]
                        logger.warning(f"⚠️ Schema drift detected: {drift}")
                        
                        # Save detected schema for documentation
                        self.schema_validator.save_detected_schema(self.df)
                
                except (SchemaError, DataValidationError) as e:
                    logger.error(f"❌ Schema validation failed: {e}")
                    
                    # Save detected schema for debugging
                    if hasattr(self, 'schema_validator'):
                        try:
                            schema_path = self.schema_validator.save_detected_schema(self.df)
                            logger.info(f"Actual schema saved to {schema_path} for debugging")
                        except Exception as save_error:
                            logger.error(f"Failed to save detected schema: {save_error}")
                    
                    raise
            
            # Sample if needed
            if self.use_sample and len(self.df) > self.sample_size:
                logger.info(f"Sampling {self.sample_size} rows")
                self.df = self.df.sample(n=self.sample_size, random_state=42)
            
            logger.info(f"Loaded {len(self.df)} rows, {len(self.df.columns)} columns")
            return self.df
            
        except FileNotFoundError as e:
            logger.error(f"CSV file not found: {self.csv_path}")
            raise FileNotFoundError(f"Data file not found: {self.csv_path}. Please ensure the CSV exists.")
        except pd.errors.EmptyDataError as e:
            logger.error(f"CSV file is empty: {self.csv_path}")
            raise DataValidationError(f"CSV file is empty: {self.csv_path}", invalid_rows=0)
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def _preprocess(self):
        """Basic preprocessing: date parsing, type conversion, handling nulls"""
        # Parse date column
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'])
        
        # Convert numeric columns
        numeric_cols = ['spend', 'impressions', 'clicks', 'ctr', 'purchases', 'revenue', 'roas']
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        
        # Handle missing values - fill with 0 for metrics
        metric_cols = ['spend', 'impressions', 'clicks', 'purchases', 'revenue']
        for col in metric_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].fillna(0)
        
        # Normalize campaign names (handle inconsistent spacing/caps)
        if 'campaign_name' in self.df.columns:
            self.df['campaign_name_clean'] = (
                self.df['campaign_name']
                .str.strip()
                .str.replace(r'\s+', ' ', regex=True)
                .str.title()
            )
        
        logger.info("Preprocessing complete")
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate high-level summary statistics for LLM consumption"""
        if self.df is None:
            raise ValueError("Data not loaded. Call load() first.")
        
        summary = {
            "total_rows": len(self.df),
            "date_range": {
                "start": str(self.df['date'].min().date()) if 'date' in self.df.columns else None,
                "end": str(self.df['date'].max().date()) if 'date' in self.df.columns else None,
                "days": int((self.df['date'].max() - self.df['date'].min()).days) if 'date' in self.df.columns else None
            },
            "campaigns": {
                "count": self.df['campaign_name'].nunique() if 'campaign_name' in self.df.columns else 0,
                "names": self.df['campaign_name'].unique().tolist()[:5] if 'campaign_name' in self.df.columns else []
            },
            "metrics": {
                "total_spend": float(self.df['spend'].sum()) if 'spend' in self.df.columns else 0,
                "total_impressions": int(self.df['impressions'].sum()) if 'impressions' in self.df.columns else 0,
                "total_clicks": int(self.df['clicks'].sum()) if 'clicks' in self.df.columns else 0,
                "total_purchases": int(self.df['purchases'].sum()) if 'purchases' in self.df.columns else 0,
                "total_revenue": float(self.df['revenue'].sum()) if 'revenue' in self.df.columns else 0,
                "avg_ctr": float(self.df['ctr'].mean()) if 'ctr' in self.df.columns else 0,
                "avg_roas": float(self.df['roas'].mean()) if 'roas' in self.df.columns else 0
            },
            "dimensions": {
                "creative_types": self.df['creative_type'].value_counts().to_dict() if 'creative_type' in self.df.columns else {},
                "platforms": self.df['platform'].value_counts().to_dict() if 'platform' in self.df.columns else {},
                "countries": self.df['country'].value_counts().to_dict() if 'country' in self.df.columns else {},
                "audience_types": self.df['audience_type'].value_counts().to_dict() if 'audience_type' in self.df.columns else {}
            }
        }
        
        return summary
    
    def get_time_series_summary(self, metric: str = 'roas', window: int = 7) -> Dict[str, Any]:
        """Get time series summary for trend analysis"""
        if self.df is None or 'date' not in self.df.columns:
            return {}
        
        daily = self.df.groupby('date').agg({
            'spend': 'sum',
            'revenue': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'purchases': 'sum'
        }).reset_index()
        
        # Calculate ROAS
        daily['roas'] = daily['revenue'] / daily['spend'].replace(0, np.nan)
        daily['ctr'] = daily['clicks'] / daily['impressions'].replace(0, np.nan)
        
        # Recent vs previous comparison
        recent = daily.tail(window)
        previous = daily.head(len(daily) - window).tail(window)
        
        return {
            "recent_avg": float(recent[metric].mean()) if len(recent) > 0 else 0,
            "previous_avg": float(previous[metric].mean()) if len(previous) > 0 else 0,
            "change_pct": float(
                ((recent[metric].mean() - previous[metric].mean()) / previous[metric].mean() * 100)
                if len(previous) > 0 and previous[metric].mean() != 0 else 0
            ),
            "trend": "increasing" if recent[metric].mean() > previous[metric].mean() else "decreasing"
        }
