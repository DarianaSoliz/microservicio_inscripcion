"""
Saga Pattern Implementation
Manages distributed transactions with automatic compensation
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import json
import time

class SagaStepStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    COMPENSATED = "compensated"
    FAILED = "failed"

@dataclass
class SagaStep:
    step_id: str
    name: str
    action: Callable[..., Awaitable[Any]]
    compensation: Callable[..., Awaitable[None]]
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    action_kwargs: Dict[str, Any] = field(default_factory=dict)
    compensation_kwargs: Dict[str, Any] = field(default_factory=dict)

class SagaTransaction:
    """Manages a saga transaction with automatic compensation"""
    
    def __init__(self, saga_id: str, correlation_id: Optional[str] = None):
        self.saga_id = saga_id
        self.correlation_id = correlation_id
        self.steps: List[SagaStep] = []
        self.completed_steps: List[SagaStep] = []
        self.status = "pending"
        self.created_at = time.time()

    async def add_step(
        self,
        name: str,
        action: Callable[..., Awaitable[Any]],
        compensation: Callable[..., Awaitable[None]],
        **action_kwargs
    ) -> str:
        """Add a step to the saga"""
        step_id = f"{self.saga_id}_{len(self.steps)}"
        
        step = SagaStep(
            step_id=step_id,
            name=name,
            action=action,
            compensation=compensation,
            action_kwargs=action_kwargs
        )
        
        self.steps.append(step)
        return step_id

    async def execute(self) -> Dict[str, Any]:
        """Execute all saga steps"""
        results = {}
        
        try:
            for step in self.steps:
                try:
                    # Execute the step
                    step.result = await step.action(**step.action_kwargs)
                    step.status = SagaStepStatus.COMPLETED
                    self.completed_steps.append(step)
                    results[step.name] = step.result
                    
                except Exception as e:
                    step.status = SagaStepStatus.FAILED
                    step.error = str(e)
                    # If any step fails, compensate all completed steps
                    await self.compensate()
                    raise SagaExecutionException(f"Saga step '{step.name}' failed: {str(e)}")
            
            self.status = "completed"
            return results
            
        except Exception as e:
            self.status = "failed"
            raise

    async def compensate(self) -> None:
        """Compensate all completed steps in reverse order"""
        compensation_errors = []
        
        # Compensate in reverse order
        for step in reversed(self.completed_steps):
            if step.status == SagaStepStatus.COMPLETED:
                try:
                    # Prepare compensation kwargs
                    compensation_kwargs = step.compensation_kwargs.copy()
                    # Add result data to compensation if needed
                    if step.result and isinstance(step.result, dict):
                        compensation_kwargs.update(step.result)
                    
                    await step.compensation(**compensation_kwargs)
                    step.status = SagaStepStatus.COMPENSATED
                    
                except Exception as e:
                    compensation_errors.append(f"Compensation failed for step '{step.name}': {str(e)}")
                    # Continue compensating other steps even if one fails
        
        self.status = "compensated"
        
        if compensation_errors:
            # Log compensation errors but don't raise
            print(f"Saga compensation errors: {compensation_errors}")

    def get_status(self) -> Dict[str, Any]:
        """Get saga status"""
        return {
            "saga_id": self.saga_id,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "created_at": self.created_at,
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": step.status.value,
                    "error": step.error
                }
                for step in self.steps
            ]
        }

class SagaExecutionException(Exception):
    """Exception raised when saga execution fails"""
    pass

class InscriptionSagaOrchestrator:
    """Orchestrates inscription-related sagas"""
    
    def __init__(self):
        self.active_sagas: Dict[str, SagaTransaction] = {}

    async def create_inscription_saga(
        self,
        inscription_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> SagaTransaction:
        """Create a new inscription saga"""
        saga_id = f"inscription_saga_{uuid.uuid4()}"
        saga = SagaTransaction(saga_id, correlation_id)
        
        self.active_sagas[saga_id] = saga
        return saga

    async def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific saga"""
        saga = self.active_sagas.get(saga_id)
        return saga.get_status() if saga else None

    async def get_active_sagas(self) -> Dict[str, Any]:
        """Get all active sagas"""
        return {
            saga_id: saga.get_status() 
            for saga_id, saga in self.active_sagas.items()
        }

    async def cleanup_completed_sagas(self, max_age_hours: int = 24) -> int:
        """Clean up old completed sagas"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        sagas_to_remove = []
        for saga_id, saga in self.active_sagas.items():
            if (saga.status in ["completed", "compensated", "failed"] and 
                current_time - saga.created_at > max_age_seconds):
                sagas_to_remove.append(saga_id)
        
        for saga_id in sagas_to_remove:
            del self.active_sagas[saga_id]
        
        return len(sagas_to_remove)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get saga statistics"""
        total_sagas = len(self.active_sagas)
        status_counts = {}
        
        for saga in self.active_sagas.values():
            status = saga.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_active_sagas": total_sagas,
            "status_distribution": status_counts,
            "oldest_saga_age_hours": (
                (time.time() - min(saga.created_at for saga in self.active_sagas.values())) / 3600
                if self.active_sagas else 0
            )
        }

# Global saga manager
saga_manager = InscriptionSagaOrchestrator()