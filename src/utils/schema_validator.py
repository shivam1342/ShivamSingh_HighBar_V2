"""
Schema validation and drift detection for data governance
"""
import pandas as pd
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from src.utils.exceptions import SchemaError, DataValidationError

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates DataFrame schema against expected schema definition"""
    
    def __init__(self, schema_path: str = "config/schemas/schema_v1.yaml"):
        self.schema_path = Path(schema_path)
        self.schema = self._load_schema()
        
    def _load_schema(self) -> Dict[str, Any]:
        """Load schema definition from YAML"""
        try:
            with open(self.schema_path, 'r') as f:
                schema = yaml.safe_load(f)
            logger.info(f"Loaded schema version {schema.get('version', 'unknown')}")
            return schema
        except FileNotFoundError:
            logger.error(f"Schema file not found: {self.schema_path}")
            raise SchemaError(f"Schema definition not found: {self.schema_path}")
    
    def validate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate DataFrame against schema
        
        Args:
            df: DataFrame to validate
            
        Returns:
            Validation report with issues and warnings
            
        Raises:
            SchemaError: Critical schema violations
            DataValidationError: Data quality issues
        """
        logger.info("Starting schema validation...")
        
        validation_report = {
            "schema_version": self.schema.get("version"),
            "validation_timestamp": datetime.now().isoformat(),
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Check 1: Required columns exist
        missing_columns = self._check_required_columns(df)
        if missing_columns:
            # Try to find similar columns (renamed detection)
            suggestions = self._suggest_column_mappings(missing_columns, df.columns)
            
            # Build comprehensive error message
            error_msg = f"Schema validation failed: Missing required columns: {missing_columns}"
            
            if suggestions:
                error_msg += "\n\n💡 Possible Solutions:"
                for suggestion in suggestions:
                    error_msg += f"\n   • {suggestion}"
                error_msg += "\n\n🔧 Action Required: Update your CSV column names to match the schema."
                validation_report["suggestions"].extend(suggestions)
                logger.warning(f"Missing columns detected. Suggestions: {suggestions}")
            else:
                error_msg += f"\n\n❌ No similar columns found in CSV."
                error_msg += f"\n📋 Expected columns: {list(self.schema.get('required_columns', {}).keys())}"
                error_msg += f"\n📋 Actual columns: {list(df.columns)}"
                error_msg += "\n\n🔧 Action Required: Check your CSV file and schema definition."
            
            validation_report["errors"].append(error_msg)
            
            raise SchemaError(
                error_msg,
                expected_schema=self._get_expected_columns(),
                actual_schema=list(df.columns)
            )
        
        # Check 2: Data types match
        type_mismatches = self._check_data_types(df)
        if type_mismatches:
            validation_report["warnings"].extend(type_mismatches)
            logger.warning(f"Data type mismatches: {type_mismatches}")
        
        # Check 3: Value ranges
        range_violations = self._check_value_ranges(df)
        if range_violations:
            validation_report["errors"].extend(range_violations)
        
        # Check 4: Data quality rules
        quality_issues = self._check_data_quality(df)
        if quality_issues:
            validation_report["warnings"].extend(quality_issues)
        
        # Check 5: Schema drift detection
        drift = self._detect_schema_drift(df)
        if drift:
            validation_report["drift_detected"] = drift
            logger.warning(f"Schema drift detected: {drift}")
        
        # Fail if critical errors
        if validation_report["errors"]:
            error_summary = "\n".join(validation_report["errors"])
            raise DataValidationError(
                f"Data validation failed:\n{error_summary}",
                invalid_rows=len(df)
            )
        
        logger.info("Schema validation passed")
        return validation_report
    
    def _check_required_columns(self, df: pd.DataFrame) -> List[str]:
        """Check if all required columns are present"""
        required_cols = self.schema.get("required_columns", {}).keys()
        missing = [col for col in required_cols if col not in df.columns]
        return missing
    
    def _suggest_column_mappings(
        self, 
        missing_columns: List[str], 
        actual_columns: List[str]
    ) -> List[str]:
        """
        Suggest possible renamed columns using fuzzy matching + semantic keywords
        
        Returns suggestions like:
        "Column 'spend' missing. Did you mean 'ad_spend'? (similarity: 85%)"
        "Column 'revenue' missing. Did you mean 'sales_amount'? (contains: 'amount' - likely revenue)"
        """
        suggestions = []
        threshold = 0.3  # 30% similarity threshold (catches more potential renames)
        
        # Semantic keyword mappings for common column types
        semantic_keywords = {
            'revenue': ['sales', 'amount', 'income', 'earnings'],
            'spend': ['cost', 'budget', 'expense'],
            'clicks': ['click', 'tap'],
            'impressions': ['impression', 'views', 'reach'],
            'purchases': ['conversion', 'order', 'transaction', 'buy']
        }
        
        for missing in missing_columns:
            best_match = None
            best_score = 0
            match_reason = "similarity"
            
            # Check 1: Semantic keyword matching (PRIORITIZE THIS)
            if missing.lower() in semantic_keywords:
                keywords = semantic_keywords[missing.lower()]
                for actual in actual_columns:
                    for keyword in keywords:
                        if keyword in actual.lower():
                            semantic_score = 0.9  # High score for semantic matches
                            if semantic_score > best_score:
                                best_score = semantic_score
                                best_match = actual
                                match_reason = f"contains '{keyword}' (likely {missing})"
                                break
            
            # Check 2: Fuzzy string matching (fallback)
            if best_score < 0.9:  # Only if no semantic match found
                for actual in actual_columns:
                    score = SequenceMatcher(None, missing.lower(), actual.lower()).ratio()
                    
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = actual
                        match_reason = "similarity"
            
            if best_match:
                if match_reason == "similarity":
                    suggestions.append(
                        f"Column '{missing}' missing. Did you mean '{best_match}'? "
                        f"(similarity: {best_score * 100:.0f}%)"
                    )
                else:
                    suggestions.append(
                        f"Column '{missing}' missing. Did you mean '{best_match}'? "
                        f"({match_reason})"
                    )
        
        return suggestions
    
    def _check_data_types(self, df: pd.DataFrame) -> List[str]:
        """Check if column data types match expected types"""
        mismatches = []
        
        all_columns = {**self.schema.get("required_columns", {}), 
                       **self.schema.get("optional_columns", {})}
        
        for col_name, col_spec in all_columns.items():
            if col_name not in df.columns:
                continue  # Already handled in required check
            
            expected_type = col_spec.get("type")
            actual_type = str(df[col_name].dtype)
            
            # Handle datetime special case
            if expected_type == "datetime64" and not pd.api.types.is_datetime64_any_dtype(df[col_name]):
                mismatches.append(
                    f"Column '{col_name}': expected datetime, got {actual_type}"
                )
            elif expected_type in ["float64", "int64"] and not pd.api.types.is_numeric_dtype(df[col_name]):
                mismatches.append(
                    f"Column '{col_name}': expected numeric ({expected_type}), got {actual_type}"
                )
        
        return mismatches
    
    def _check_value_ranges(self, df: pd.DataFrame) -> List[str]:
        """Check if values are within expected ranges"""
        violations = []
        
        all_columns = {**self.schema.get("required_columns", {}), 
                       **self.schema.get("optional_columns", {})}
        
        for col_name, col_spec in all_columns.items():
            if col_name not in df.columns:
                continue
            
            # Check minimum value
            if "min_value" in col_spec:
                min_val = col_spec["min_value"]
                if (df[col_name] < min_val).any():
                    count = (df[col_name] < min_val).sum()
                    violations.append(
                        f"Column '{col_name}': {count} values below minimum ({min_val})"
                    )
            
            # Check maximum value
            if "max_value" in col_spec:
                max_val = col_spec["max_value"]
                if (df[col_name] > max_val).any():
                    count = (df[col_name] > max_val).sum()
                    violations.append(
                        f"Column '{col_name}': {count} values above maximum ({max_val})"
                    )
        
        return violations
    
    def _check_data_quality(self, df: pd.DataFrame) -> List[str]:
        """Check data quality rules"""
        issues = []
        rules = self.schema.get("validation_rules", {})
        
        # Check minimum rows
        min_rows = rules.get("min_rows", 0)
        if len(df) < min_rows:
            issues.append(f"Insufficient data: {len(df)} rows (minimum: {min_rows})")
        
        # Check missing values percentage
        max_missing_pct = rules.get("max_missing_percentage", 100)
        for col in df.columns:
            missing_pct = (df[col].isna().sum() / len(df)) * 100
            if missing_pct > max_missing_pct:
                issues.append(
                    f"Column '{col}': {missing_pct:.1f}% missing values "
                    f"(max allowed: {max_missing_pct}%)"
                )
        
        # Check date range
        if 'date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['date']):
            date_range = (df['date'].max() - df['date'].min()).days
            max_days = rules.get("date_range_max_days", 365)
            if date_range > max_days:
                issues.append(
                    f"Date range too large: {date_range} days (max: {max_days})"
                )
        
        return issues
    
    def _detect_schema_drift(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect unexpected schema changes"""
        expected_cols = set(self._get_expected_columns())
        actual_cols = set(df.columns)
        
        drift = {}
        
        # New columns (not in schema)
        new_columns = actual_cols - expected_cols
        if new_columns:
            drift["new_columns"] = list(new_columns)
        
        # Removed optional columns
        optional_cols = set(self.schema.get("optional_columns", {}).keys())
        removed_optional = optional_cols - actual_cols
        if removed_optional:
            drift["removed_optional_columns"] = list(removed_optional)
        
        return drift if drift else None
    
    def _get_expected_columns(self) -> List[str]:
        """Get list of all expected column names"""
        required = list(self.schema.get("required_columns", {}).keys())
        optional = list(self.schema.get("optional_columns", {}).keys())
        return required + optional
    
    def save_detected_schema(self, df: pd.DataFrame, output_path: str = None):
        """
        Save detected schema as new version for documentation
        
        Args:
            df: DataFrame with actual schema
            output_path: Where to save detected schema
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"config/schemas/schema_detected_{timestamp}.yaml"
        
        detected_schema = {
            "version": f"{self.schema.get('version', '1.0')}_detected",
            "detected_date": datetime.now().isoformat(),
            "source_schema": self.schema.get('version'),
            "columns": {}
        }
        
        for col in df.columns:
            detected_schema["columns"][col] = {
                "type": str(df[col].dtype),
                "non_null_count": int(df[col].notna().sum()),
                "null_count": int(df[col].isna().sum()),
                "unique_count": int(df[col].nunique())
            }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            yaml.dump(detected_schema, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Detected schema saved to {output_path}")
        return output_path
