"""
StateMachine - Manages pipeline state transitions.

States:
- INITIALIZED: Pipeline created but not started
- RUNNING: Pipeline is executing
- COMPLETED: All stages completed successfully
- FAILED: Pipeline failed with error

Transitions:
- initialize() -> INITIALIZED
- start() -> RUNNING
- transition_to_completed() -> COMPLETED
- transition_to_failed(reason) -> FAILED
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StateMachine:
    """
    Manages pipeline state transitions.
    
    Ensures valid state flow: INITIALIZED → RUNNING → COMPLETED/FAILED
    """
    
    VALID_STATES = {'INITIALIZED', 'RUNNING', 'COMPLETED', 'FAILED'}
    
    def __init__(self, pipeline_config: dict):
        """
        Initialize state machine.
        
        Args:
            pipeline_config: Pipeline configuration (for logging)
        """
        self.pipeline_config = pipeline_config
        self.current_state: str = 'INITIALIZED'
        self.failure_reason: Optional[str] = None
        self.state_history: list = []
    
    def initialize(self) -> None:
        """Set pipeline to INITIALIZED state."""
        self._transition('INITIALIZED')
    
    def start(self) -> None:
        """Transition from INITIALIZED to RUNNING."""
        if self.current_state != 'INITIALIZED':
            raise ValueError(f"Cannot start from state: {self.current_state}")
        
        self._transition('RUNNING')
    
    def transition_to_completed(self) -> None:
        """Mark pipeline as successfully completed."""
        if self.current_state != 'RUNNING':
            logger.warning(f"Transitioning to COMPLETED from non-RUNNING state: {self.current_state}")
        
        self._transition('COMPLETED')
    
    def transition_to_failed(self, reason: str) -> None:
        """
        Mark pipeline as failed.
        
        Args:
            reason: Failure reason
        """
        self.failure_reason = reason
        self._transition('FAILED')
    
    def _transition(self, new_state: str) -> None:
        """
        Execute state transition.
        
        Args:
            new_state: Target state
        """
        if new_state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}")
        
        old_state = self.current_state
        self.current_state = new_state
        
        # Record transition
        self.state_history.append({
            'from': old_state,
            'to': new_state,
            'reason': self.failure_reason if new_state == 'FAILED' else None
        })
        
        logger.debug(f"State transition: {old_state} -> {new_state}")
    
    def is_running(self) -> bool:
        """Check if pipeline is currently running."""
        return self.current_state == 'RUNNING'
    
    def is_completed(self) -> bool:
        """Check if pipeline completed successfully."""
        return self.current_state == 'COMPLETED'
    
    def is_failed(self) -> bool:
        """Check if pipeline failed."""
        return self.current_state == 'FAILED'
    
    def get_state_summary(self) -> dict:
        """
        Get state summary for logging.
        
        Returns:
            Dict with current state and history
        """
        return {
            'current_state': self.current_state,
            'failure_reason': self.failure_reason,
            'state_history': self.state_history
        }
