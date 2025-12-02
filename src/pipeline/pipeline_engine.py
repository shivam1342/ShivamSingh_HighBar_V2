"""
PipelineEngine - Declarative execution engine for multi-agent workflows.

Replaces procedural orchestration with config-driven execution:
- Loads pipeline from config/pipeline.yaml
- Validates agent outputs against config/agent_contracts.yaml
- Handles retries, timeouts, and state transitions
- Provides stage-by-stage execution for testing
"""

import time
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .state_machine import StateMachine
from .schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    Executes declarative pipelines defined in YAML config.
    
    Key responsibilities:
    1. Load pipeline stages from config
    2. Execute stages in sequence with timing
    3. Validate outputs against schemas
    4. Handle retries and conditional transitions
    5. Manage pipeline state (INITIALIZED → RUNNING → COMPLETED)
    """
    
    def __init__(self, config_path: str = None, contracts_path: str = None):
        """
        Initialize pipeline engine.
        
        Args:
            config_path: Path to pipeline.yaml (default: config/pipeline.yaml)
            contracts_path: Path to agent_contracts.yaml (default: config/agent_contracts.yaml)
        """
        self.config_path = config_path or self._default_config_path()
        self.contracts_path = contracts_path or self._default_contracts_path()
        
        # Load configs
        self.pipeline_config = self._load_config(self.config_path)
        self.contracts_config = self._load_config(self.contracts_path)
        
        # Initialize components
        self.state_machine = StateMachine(self.pipeline_config)
        self.schema_validator = SchemaValidator(self.contracts_config)
        
        # Runtime state
        self.context: Dict[str, Any] = {}
        self.stage_outputs: Dict[str, Any] = {}  # stage_id -> output
        self.stage_timings: Dict[str, float] = {}  # stage_id -> duration
        self.retry_counts: Dict[str, int] = {}  # stage_id -> retry_count
        
        logger.info(f"PipelineEngine initialized: {self.pipeline_config['pipeline']['name']} v{self.pipeline_config['pipeline']['version']}")
    
    def _default_config_path(self) -> str:
        """Get default path to pipeline.yaml."""
        return str(Path(__file__).parent.parent.parent / "config" / "pipeline.yaml")
    
    def _default_contracts_path(self) -> str:
        """Get default path to agent_contracts.yaml."""
        return str(Path(__file__).parent.parent.parent / "config" / "agent_contracts.yaml")
    
    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load YAML config file."""
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def execute(self, context: Dict[str, Any], agents: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute full pipeline with all stages.
        
        Args:
            context: Initial context with user_query, raw_data, etc.
            agents: Dictionary of agent instances {agent_name: agent_instance}
                   e.g., {"planner": planner_agent, "data": data_agent, ...}
        
        Returns:
            Dict with final output (insights, creatives, evaluation)
        """
        self.context = context
        self.agents = agents
        
        # Initialize state machine
        self.state_machine.initialize()
        
        logger.info("=" * 80)
        logger.info(f"PIPELINE EXECUTION START: {self.pipeline_config['pipeline']['name']}")
        logger.info("=" * 80)
        
        pipeline_start = time.time()
        
        try:
            # Execute all stages
            for stage_config in self.pipeline_config['pipeline']['stages']:
                stage_id = stage_config['id']
                
                # Execute stage (handles retries internally)
                self._execute_stage_with_retry(stage_config)
                
                # Check if pipeline should continue
                if not self._should_continue(stage_config):
                    logger.warning(f"Pipeline stopped at stage: {stage_id}")
                    break
            
            # Mark pipeline as completed
            self.state_machine.transition_to_completed()
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            self.state_machine.transition_to_failed(str(e))
            raise
        
        finally:
            pipeline_duration = time.time() - pipeline_start
            logger.info("=" * 80)
            logger.info(f"PIPELINE EXECUTION END: {pipeline_duration:.2f}s")
            logger.info(f"Final state: {self.state_machine.current_state}")
            logger.info("=" * 80)
        
        return self._build_final_output()
    
    def _execute_stage_with_retry(self, stage_config: Dict[str, Any]) -> None:
        """
        Execute a single stage with retry logic.
        
        Args:
            stage_config: Stage configuration from pipeline.yaml
        """
        stage_id = stage_config['id']
        max_retries = stage_config.get('retry', {}).get('max_retries', 1) if stage_config.get('retry', {}).get('enabled') else 1
        
        for attempt in range(max_retries):
            try:
                # Log retry attempt
                if attempt > 0:
                    logger.info(f"[RETRY] Stage: {stage_id} (attempt {attempt + 1}/{max_retries})")
                
                # Execute stage
                output = self._execute_stage(stage_config)
                
                # Check if retry is needed based on output
                if self._needs_retry(stage_config, output, attempt, max_retries):
                    logger.warning(f"Stage {stage_id} triggered retry condition")
                    self.retry_counts[stage_id] = attempt + 1
                    continue
                
                # Success - break retry loop
                break
                
            except Exception as e:
                logger.error(f"Stage {stage_id} failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise
    
    def _execute_stage(self, stage_config: Dict[str, Any]) -> Any:
        """
        Execute a single pipeline stage.
        
        Args:
            stage_config: Stage configuration from pipeline.yaml
        
        Returns:
            Stage output (validated against schema)
        """
        stage_id = stage_config['id']
        stage_name = stage_config['name']
        agent_name = stage_config['agent']
        method_name = stage_config['method']
        timeout = stage_config.get('timeout', 30)
        
        logger.info("-" * 80)
        logger.info(f"STAGE: {stage_id} | {stage_name}")
        logger.info(f"Agent: {agent_name}.{method_name}() | Timeout: {timeout}s")
        
        stage_start = time.time()
        
        # Resolve inputs
        inputs = self._resolve_inputs(stage_config)
        logger.debug(f"Inputs resolved: {list(inputs.keys())}")
        
        # Get agent and method
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found in agents dict")
        
        method = getattr(agent, method_name, None)
        if not method:
            raise ValueError(f"Method '{method_name}' not found on agent '{agent_name}'")
        
        # Execute method
        try:
            output = method(**inputs)
        except Exception as e:
            stage_duration = time.time() - stage_start
            logger.error(f"Stage {stage_id} execution failed: {e} ({stage_duration:.2f}s)")
            raise
        
        stage_duration = time.time() - stage_start
        self.stage_timings[stage_id] = stage_duration
        
        logger.info(f"Stage completed: {stage_duration:.2f}s")
        
        # Validate output (if schema exists)
        self._validate_output(stage_config, output)
        
        # Store output
        self.stage_outputs[stage_id] = output
        
        return output
    
    def _resolve_inputs(self, stage_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve inputs for a stage from context or prior stage outputs.
        
        Input format in config:
          - "context:user_query" -> self.context["user_query"]
          - "stage:planning" -> self.stage_outputs["planning"]
          - "stage:planning.data_quality" -> self.stage_outputs["planning"]["data_quality"]
        
        Args:
            stage_config: Stage configuration with 'inputs' list
        
        Returns:
            Dict of resolved inputs {param_name: value}
        """
        resolved = {}
        
        for input_spec in stage_config.get('inputs', []):
            param_name = input_spec['name']
            source = input_spec['source']
            
            # Parse source (e.g., "context:user_query" or "stage:planning.data_quality")
            source_type, source_path = source.split(':', 1)
            
            if source_type == 'context':
                # Get from context
                resolved[param_name] = self.context.get(source_path)
            
            elif source_type == 'stage':
                # Get from prior stage output
                if '.' in source_path:
                    # Nested access (e.g., "planning.data_quality")
                    stage_id, *keys = source_path.split('.')
                    value = self.stage_outputs.get(stage_id)
                    for key in keys:
                        value = value.get(key) if isinstance(value, dict) else None
                    resolved[param_name] = value
                else:
                    # Direct access (e.g., "planning")
                    resolved[param_name] = self.stage_outputs.get(source_path)
            
            else:
                raise ValueError(f"Unknown source type: {source_type}")
            
            # Check if required input is missing
            if input_spec.get('required', True) and resolved[param_name] is None:
                raise ValueError(f"Required input '{param_name}' not found: {source}")
        
        return resolved
    
    def _validate_output(self, stage_config: Dict[str, Any], output: Any) -> None:
        """
        Validate stage output against schema.
        
        Args:
            stage_config: Stage configuration with 'outputs' list
            output: Actual output from stage
        """
        if not self.pipeline_config['pipeline']['settings'].get('validate_schemas', True):
            return
        
        for output_spec in stage_config.get('outputs', []):
            output_name = output_spec['name']
            schema_name = output_spec.get('schema')
            
            if not schema_name:
                continue  # No schema defined
            
            # Get output value (output can be dict or direct value)
            if isinstance(output, dict):
                output_value = output.get(output_name)
            else:
                output_value = output
            
            # Validate against schema
            is_valid, errors = self.schema_validator.validate(output_value, schema_name)
            
            if not is_valid:
                error_msg = f"Schema validation failed for {output_name} ({schema_name}): {errors}"
                logger.error(error_msg)
                
                if self.contracts_config['validation'].get('strict_mode', True):
                    raise ValueError(error_msg)
                else:
                    logger.warning(f"Continuing despite validation failure (strict_mode=false)")
    
    def _needs_retry(self, stage_config: Dict[str, Any], output: Any, attempt: int, max_retries: int) -> bool:
        """
        Check if stage should be retried based on output.
        
        Looks for retry conditions defined in transitions (e.g., evaluation.pass_threshold == false).
        
        Args:
            stage_config: Stage configuration
            output: Stage output
            attempt: Current attempt number (0-indexed)
            max_retries: Maximum retry attempts
        
        Returns:
            True if retry needed, False otherwise
        """
        if attempt >= max_retries - 1:
            return False  # Max retries reached
        
        stage_id = stage_config['id']
        
        # Check transitions for retry conditions
        for transition in self.pipeline_config['pipeline'].get('transitions', []):
            if transition['from'] == stage_id and transition.get('condition'):
                # Evaluate condition (e.g., "pass_threshold == false")
                condition = transition['condition']
                
                # Simple condition parser (field == value)
                if '==' in condition:
                    field, expected = condition.split('==')
                    field = field.strip()
                    expected = expected.strip().lower() == 'true'
                    
                    # Get field value from output
                    if isinstance(output, dict):
                        actual = output.get(field)
                        
                        # Check if retry needed
                        if actual == expected:
                            logger.info(f"Retry condition met: {condition}")
                            return True
        
        return False
    
    def _should_continue(self, stage_config: Dict[str, Any]) -> bool:
        """
        Check if pipeline should continue after this stage.
        
        Args:
            stage_config: Stage configuration
        
        Returns:
            True if pipeline should continue, False to stop
        """
        fail_fast = self.pipeline_config['pipeline']['settings'].get('fail_fast', False)
        
        if fail_fast and self.state_machine.current_state == 'FAILED':
            return False
        
        return True
    
    def _build_final_output(self) -> Dict[str, Any]:
        """
        Build final output from stage outputs.
        
        Returns:
            Dict with final results
        """
        return {
            'insights': self.stage_outputs.get('insight_generation', []),
            'evaluation': self.stage_outputs.get('evaluation', {}),
            'creatives': self.stage_outputs.get('creative_generation', []),
            'stage_timings': self.stage_timings,
            'retry_counts': self.retry_counts,
            'state': self.state_machine.current_state
        }
