"""
SchemaValidator - Validates agent outputs against YAML schemas.

Uses JSON Schema for validation, supporting:
- Type validation (string, number, array, object)
- Required fields
- Min/max constraints
- Enum values
- Nested object validation
- Custom validation rules
"""

import logging
from typing import Any, Tuple, List

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Validates data against schemas defined in agent_contracts.yaml.
    
    Uses JSON Schema-like validation with custom rules.
    """
    
    def __init__(self, contracts_config: dict):
        """
        Initialize validator.
        
        Args:
            contracts_config: Loaded agent_contracts.yaml config
        """
        self.contracts_config = contracts_config
        self.schemas = contracts_config.get('schemas', {})
        self.validation_rules = contracts_config.get('validation', {})
    
    def validate(self, data: Any, schema_name: str) -> Tuple[bool, List[str]]:
        """
        Validate data against schema.
        
        Args:
            data: Data to validate
            schema_name: Name of schema in agent_contracts.yaml
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if schema_name not in self.schemas:
            logger.warning(f"Schema not found: {schema_name}")
            return (True, [])  # Skip validation if schema missing
        
        schema = self.schemas[schema_name]
        errors = []
        
        # Validate against schema
        self._validate_type(data, schema, errors, path=schema_name)
        
        # Apply custom rules
        if self.validation_rules.get('custom_rules'):
            self._apply_custom_rules(data, schema_name, errors)
        
        is_valid = len(errors) == 0
        
        if not is_valid and self.validation_rules.get('log_warnings', True):
            logger.warning(f"Validation failed for {schema_name}: {errors}")
        
        return (is_valid, errors)
    
    def _validate_type(self, data: Any, schema: dict, errors: List[str], path: str) -> None:
        """
        Validate data type and structure.
        
        Args:
            data: Data to validate
            schema: Schema definition
            errors: List to append errors to
            path: Current validation path (for error messages)
        """
        expected_type = schema.get('type')
        
        # Type validation
        if expected_type == 'object':
            if not isinstance(data, dict):
                errors.append(f"{path}: Expected object, got {type(data).__name__}")
                return
            
            # Validate required fields
            required = schema.get('required', [])
            for field in required:
                if field not in data:
                    errors.append(f"{path}.{field}: Required field missing")
            
            # Validate properties
            properties = schema.get('properties', {})
            for field, field_schema in properties.items():
                if field in data:
                    self._validate_type(data[field], field_schema, errors, f"{path}.{field}")
        
        elif expected_type == 'array':
            if not isinstance(data, list):
                errors.append(f"{path}: Expected array, got {type(data).__name__}")
                return
            
            # Validate array constraints
            min_items = schema.get('minItems')
            max_items = schema.get('maxItems')
            
            if min_items is not None and len(data) < min_items:
                errors.append(f"{path}: Array too short (min {min_items}, got {len(data)})")
            
            if max_items is not None and len(data) > max_items:
                errors.append(f"{path}: Array too long (max {max_items}, got {len(data)})")
            
            # Validate items
            items_schema = schema.get('items')
            if items_schema:
                for i, item in enumerate(data):
                    self._validate_type(item, items_schema, errors, f"{path}[{i}]")
        
        elif expected_type == 'string':
            if not isinstance(data, str):
                errors.append(f"{path}: Expected string, got {type(data).__name__}")
                return
            
            # Validate string constraints
            min_length = schema.get('minLength')
            max_length = schema.get('maxLength')
            enum = schema.get('enum')
            
            if min_length is not None and len(data) < min_length:
                errors.append(f"{path}: String too short (min {min_length}, got {len(data)})")
            
            if max_length is not None and len(data) > max_length:
                errors.append(f"{path}: String too long (max {max_length}, got {len(data)})")
            
            if enum and data not in enum:
                errors.append(f"{path}: Invalid enum value (expected one of {enum}, got '{data}')")
        
        elif expected_type == 'number':
            if not isinstance(data, (int, float)):
                errors.append(f"{path}: Expected number, got {type(data).__name__}")
                return
            
            # Validate number constraints
            minimum = schema.get('minimum')
            maximum = schema.get('maximum')
            
            if minimum is not None and data < minimum:
                errors.append(f"{path}: Number too small (min {minimum}, got {data})")
            
            if maximum is not None and data > maximum:
                errors.append(f"{path}: Number too large (max {maximum}, got {data})")
        
        elif expected_type == 'integer':
            if not isinstance(data, int):
                errors.append(f"{path}: Expected integer, got {type(data).__name__}")
                return
            
            # Validate integer constraints
            minimum = schema.get('minimum')
            maximum = schema.get('maximum')
            
            if minimum is not None and data < minimum:
                errors.append(f"{path}: Integer too small (min {minimum}, got {data})")
            
            if maximum is not None and data > maximum:
                errors.append(f"{path}: Integer too large (max {maximum}, got {data})")
        
        elif expected_type == 'boolean':
            if not isinstance(data, bool):
                errors.append(f"{path}: Expected boolean, got {type(data).__name__}")
    
    def _apply_custom_rules(self, data: Any, schema_name: str, errors: List[str]) -> None:
        """
        Apply custom validation rules.
        
        Args:
            data: Data to validate
            schema_name: Schema being validated
            errors: List to append errors to
        """
        custom_rules = self.validation_rules.get('custom_rules', [])
        
        for rule in custom_rules:
            if rule['applies_to'] != schema_name:
                continue
            
            rule_name = rule['name']
            rule_expr = rule['rule']
            
            # Simple rule evaluator (extend as needed)
            try:
                if rule_name == 'confidence_evidence_correlation':
                    # High confidence requires more evidence
                    if isinstance(data, list):
                        for i, item in enumerate(data):
                            if isinstance(item, dict):
                                confidence = item.get('confidence', 0)
                                evidence = item.get('evidence', [])
                                if confidence > 0.8 and len(evidence) < 3:
                                    errors.append(f"Item {i}: High confidence ({confidence}) requires at least 3 pieces of evidence (got {len(evidence)})")
                
                elif rule_name == 'quality_threshold_validation':
                    # Pass threshold requires quality >= 0.7
                    if isinstance(data, dict):
                        pass_threshold = data.get('pass_threshold', False)
                        overall_quality = data.get('overall_quality', 0)
                        if pass_threshold and overall_quality < 0.7:
                            errors.append(f"Pass threshold requires quality >= 0.7 (got {overall_quality})")
                
                elif rule_name == 'validated_count_consistency':
                    # Validated count must match validated_insights length
                    if isinstance(data, dict):
                        validated_count = data.get('validated_count', 0)
                        validated_insights = data.get('validated_insights', [])
                        if validated_count != len(validated_insights):
                            errors.append(f"Validated count ({validated_count}) doesn't match insights length ({len(validated_insights)})")
            
            except Exception as e:
                logger.error(f"Custom rule '{rule_name}' failed: {e}")
