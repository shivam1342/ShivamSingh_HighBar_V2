"""
Structured logging for full observability and debugging
"""
import json
import logging
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class StructuredLogger:
    """
    Logs structured data in JSON Lines format for observability
    
    Each log entry contains:
    - timestamp
    - log level (INFO, WARNING, ERROR)
    - agent name
    - event type (start, complete, error, etc.)
    - contextual data (input, output, duration, etc.)
    """
    
    def __init__(self, log_file: str = "logs/execution.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Clear previous logs or append
        # For new runs, we'll append with session separator
        self._write_session_start()
    
    def _write_session_start(self):
        """Mark the start of a new execution session"""
        session_marker = {
            "timestamp": self._get_timestamp(),
            "level": "INFO",
            "event": "session_start",
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "message": "=" * 80
        }
        self._write_log(session_marker)
    
    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp"""
        return datetime.now().isoformat()
    
    def _write_log(self, log_entry: Dict[str, Any]):
        """Write a single log entry as JSON line"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, default=str) + '\n')
        except Exception as e:
            logger.error(f"Failed to write structured log: {e}")
    
    def log_agent_start(self, agent_name: str, input_data: Any = None, **kwargs):
        """
        Log when an agent starts processing
        
        Args:
            agent_name: Name of the agent (planner, data_agent, etc.)
            input_data: Input parameters/data passed to agent
            **kwargs: Additional context
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "INFO",
            "agent": agent_name,
            "event": "start",
            "input": input_data,
            **kwargs
        }
        self._write_log(log_entry)
        logger.info(f"[{agent_name.upper()}] Starting...")
    
    def log_agent_complete(
        self, 
        agent_name: str, 
        output_data: Any = None, 
        duration_seconds: float = None,
        **kwargs
    ):
        """
        Log when an agent completes successfully
        
        Args:
            agent_name: Name of the agent
            output_data: Output/result from agent
            duration_seconds: How long the agent took
            **kwargs: Additional context (e.g., confidence_score)
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "INFO",
            "agent": agent_name,
            "event": "complete",
            "output": output_data,
            "duration_seconds": round(duration_seconds, 3) if duration_seconds else None,
            **kwargs
        }
        self._write_log(log_entry)
        
        duration_msg = f" ({duration_seconds:.2f}s)" if duration_seconds else ""
        logger.info(f"[{agent_name.upper()}] Complete{duration_msg}")
    
    def log_agent_error(
        self, 
        agent_name: str, 
        error: Exception, 
        context: Dict[str, Any] = None,
        attempt: int = None
    ):
        """
        Log when an agent fails with error
        
        Args:
            agent_name: Name of the agent that failed
            error: The exception that occurred
            context: Additional context about what was being processed
            attempt: Retry attempt number (if applicable)
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "ERROR",
            "agent": agent_name,
            "event": "error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "attempt": attempt,
            "recoverable": getattr(error, 'recoverable', False),
            "stack_trace": traceback.format_exc().split('\n')
        }
        
        # Add error-specific attributes if available
        if hasattr(error, 'status_code'):
            log_entry["status_code"] = error.status_code
        if hasattr(error, 'raw_response'):
            log_entry["raw_response"] = error.raw_response[:500]  # Truncate long responses
        
        self._write_log(log_entry)
        logger.error(f"[{agent_name.upper()}] Error: {error}")
    
    def log_llm_call(
        self,
        agent_name: str,
        prompt: str,
        system_prompt: str = None,
        response: str = None,
        model: str = None,
        duration_seconds: float = None,
        tokens_used: int = None,
        error: Exception = None
    ):
        """
        Log LLM API calls for debugging and cost tracking
        
        Args:
            agent_name: Which agent made the call
            prompt: User prompt sent to LLM
            system_prompt: System prompt sent to LLM
            response: LLM response received
            model: Model used
            duration_seconds: API call latency
            tokens_used: Number of tokens consumed
            error: Error if call failed
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "ERROR" if error else "INFO",
            "agent": agent_name,
            "event": "llm_call",
            "model": model,
            "prompt_length": len(prompt) if prompt else 0,
            "system_prompt_length": len(system_prompt) if system_prompt else 0,
            "response_length": len(response) if response else 0,
            "duration_seconds": round(duration_seconds, 3) if duration_seconds else None,
            "tokens_used": tokens_used
        }
        
        # Include prompts for debugging (truncate if too long)
        if prompt:
            log_entry["prompt_preview"] = prompt[:200] + "..." if len(prompt) > 200 else prompt
        if response:
            log_entry["response_preview"] = response[:200] + "..." if len(response) > 200 else response
        
        if error:
            log_entry["error_type"] = type(error).__name__
            log_entry["error_message"] = str(error)
        
        self._write_log(log_entry)
    
    def log_validation(
        self,
        validation_type: str,
        passed: bool,
        details: Dict[str, Any] = None,
        **kwargs
    ):
        """
        Log validation checks (schema, quality, etc.)
        
        Args:
            validation_type: Type of validation (schema, quality, range, etc.)
            passed: Whether validation passed
            details: Details about what passed/failed
            **kwargs: Additional context
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "WARNING" if not passed else "INFO",
            "event": "validation",
            "validation_type": validation_type,
            "passed": passed,
            "details": details,
            **kwargs
        }
        self._write_log(log_entry)
        
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"[VALIDATION] {validation_type}: {status}")
    
    def log_retry_attempt(
        self,
        agent_name: str,
        attempt_number: int,
        max_attempts: int,
        reason: str,
        next_delay_seconds: float = None
    ):
        """
        Log retry attempts for failed operations
        
        Args:
            agent_name: Which agent is retrying
            attempt_number: Current attempt (1, 2, 3...)
            max_attempts: Maximum attempts allowed
            reason: Why it's retrying (error message)
            next_delay_seconds: How long until next retry
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "WARNING",
            "agent": agent_name,
            "event": "retry_attempt",
            "attempt": attempt_number,
            "max_attempts": max_attempts,
            "reason": reason,
            "next_delay_seconds": round(next_delay_seconds, 2) if next_delay_seconds else None
        }
        self._write_log(log_entry)
        
        delay_msg = f" Retrying in {next_delay_seconds:.1f}s..." if next_delay_seconds else ""
        logger.warning(
            f"[{agent_name.upper()}] Attempt {attempt_number}/{max_attempts} failed: {reason}.{delay_msg}"
        )
    
    def log_metric(
        self,
        metric_name: str,
        value: Any,
        context: Dict[str, Any] = None
    ):
        """
        Log metrics and scores (confidence, quality, performance, etc.)
        
        Args:
            metric_name: Name of metric (confidence_score, quality_score, etc.)
            value: Metric value
            context: Additional context
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "INFO",
            "event": "metric",
            "metric_name": metric_name,
            "value": value,
            "context": context
        }
        self._write_log(log_entry)
    
    def log_data_summary(
        self,
        summary_type: str,
        data: Dict[str, Any]
    ):
        """
        Log data summaries and statistics
        
        Args:
            summary_type: Type of summary (dataset, analysis_result, etc.)
            data: Summary data
        """
        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": "INFO",
            "event": "data_summary",
            "summary_type": summary_type,
            "data": data
        }
        self._write_log(log_entry)


def log_agent_execution(agent_name: str, logger_instance: StructuredLogger = None):
    """
    Decorator to automatically log agent execution (start, complete, duration, errors)
    
    Usage:
        @log_agent_execution("planner")
        def plan(self, user_query, data_summary):
            # agent logic
            return result
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use provided logger or create default
            log = logger_instance or StructuredLogger()
            
            # Extract input for logging
            input_data = {
                "args": [str(arg)[:100] for arg in args[1:]],  # Skip 'self'
                "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
            }
            
            # Log start
            log.log_agent_start(agent_name, input_data)
            
            start_time = time.time()
            
            try:
                # Execute agent function
                result = func(*args, **kwargs)
                
                # Log completion
                duration = time.time() - start_time
                
                # Try to extract confidence scores if in result
                confidence = None
                if isinstance(result, dict):
                    if 'confidence' in result:
                        confidence = result['confidence']
                    elif isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], dict) and 'confidence' in result[0]:
                            confidences = [r.get('confidence') for r in result if 'confidence' in r]
                            confidence = sum(confidences) / len(confidences) if confidences else None
                
                log.log_agent_complete(
                    agent_name,
                    output_data={"result_type": type(result).__name__, "result_size": len(result) if hasattr(result, '__len__') else None},
                    duration_seconds=duration,
                    confidence_score=confidence
                )
                
                return result
                
            except Exception as e:
                # Log error
                duration = time.time() - start_time
                log.log_agent_error(
                    agent_name,
                    error=e,
                    context={"duration_before_error": duration}
                )
                raise
        
        return wrapper
    return decorator
