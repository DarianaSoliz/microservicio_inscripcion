"""
Saga Pattern implementation for distributed transactions in inscription system
Ensures atomicity across multiple operations with automatic rollback on failure
"""
import asyncio
import enum
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union
import json
import logging

logger = logging.getLogger(__name__)


class SagaStepStatus(enum.Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class SagaStatus(enum.Enum):
    STARTED = "started"
    EXECUTING = "executing"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class SagaStepResult:
    """Result of executing a saga step"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    compensation_data: Optional[Dict[str, Any]] = None


@dataclass
class SagaStep:
    """Individual step in a saga transaction"""
    name: str
    action: Callable
    compensation: Optional[Callable] = None
    action_args: tuple = field(default_factory=tuple)
    action_kwargs: dict = field(default_factory=dict)
    compensation_args: tuple = field(default_factory=tuple)
    compensation_kwargs: dict = field(default_factory=dict)
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[SagaStepResult] = None
    executed_at: Optional[datetime] = None
    compensated_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


class SagaTransaction:
    """
    Saga transaction coordinator
    Manages execution of steps and compensation in case of failures
    """
    
    def __init__(self, transaction_id: Optional[str] = None, name: Optional[str] = None):
        self.transaction_id = transaction_id or str(uuid.uuid4())
        self.name = name or f"saga_{self.transaction_id[:8]}"
        self.steps: List[SagaStep] = []
        self.status = SagaStatus.STARTED
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.context: Dict[str, Any] = {}
    
    def add_step(
        self,
        name: str,
        action: Callable,
        compensation: Optional[Callable] = None,
        action_args: tuple = (),
        action_kwargs: Optional[dict] = None,
        compensation_args: tuple = (),
        compensation_kwargs: Optional[dict] = None,
        max_retries: int = 3
    ) -> 'SagaTransaction':
        """Add a step to the saga transaction"""
        step = SagaStep(
            name=name,
            action=action,
            compensation=compensation,
            action_args=action_args,
            action_kwargs=action_kwargs or {},
            compensation_args=compensation_args,
            compensation_kwargs=compensation_kwargs or {},
            max_retries=max_retries
        )
        self.steps.append(step)
        return self
    
    async def execute(self) -> bool:
        """
        Execute all saga steps
        Returns True if all steps completed successfully, False otherwise
        """
        self.status = SagaStatus.EXECUTING
        self.started_at = datetime.now()
        
        logger.info(f"Starting saga transaction '{self.name}' ({self.transaction_id})")
        
        try:
            # Execute each step in order
            for i, step in enumerate(self.steps):
                logger.info(f"Executing step {i+1}/{len(self.steps)}: {step.name}")
                
                success = await self._execute_step(step)
                if not success:
                    logger.error(f"Step '{step.name}' failed, initiating compensation")
                    await self._compensate_completed_steps()
                    self.status = SagaStatus.COMPENSATED
                    return False
            
            # All steps completed successfully
            self.status = SagaStatus.COMPLETED
            self.completed_at = datetime.now()
            logger.info(f"Saga transaction '{self.name}' completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Saga transaction '{self.name}' failed with exception: {e}")
            self.error = str(e)
            self.status = SagaStatus.FAILED
            await self._compensate_completed_steps()
            return False
    
    async def _execute_step(self, step: SagaStep) -> bool:
        """Execute a single saga step with retry logic"""
        step.status = SagaStepStatus.EXECUTING
        
        for attempt in range(step.max_retries + 1):
            try:
                step.retry_count = attempt
                
                # Execute the action
                if asyncio.iscoroutinefunction(step.action):
                    result = await step.action(*step.action_args, **step.action_kwargs)
                else:
                    result = step.action(*step.action_args, **step.action_kwargs)
                
                # Store result
                step.result = SagaStepResult(
                    success=True,
                    data=result,
                    compensation_data=getattr(result, 'compensation_data', None) if hasattr(result, 'compensation_data') else None
                )
                step.status = SagaStepStatus.COMPLETED
                step.executed_at = datetime.now()
                
                logger.debug(f"Step '{step.name}' completed successfully on attempt {attempt + 1}")
                return True
                
            except Exception as e:
                logger.warning(f"Step '{step.name}' failed on attempt {attempt + 1}: {e}")
                
                if attempt == step.max_retries:
                    # Final attempt failed
                    step.result = SagaStepResult(
                        success=False,
                        error=str(e)
                    )
                    step.status = SagaStepStatus.FAILED
                    return False
                
                # Wait before retry (exponential backoff)
                await asyncio.sleep(2 ** attempt)
        
        return False
    
    async def _compensate_completed_steps(self):
        """Compensate all completed steps in reverse order"""
        self.status = SagaStatus.COMPENSATING
        logger.info(f"Compensating saga transaction '{self.name}'")
        
        # Compensate in reverse order
        for step in reversed(self.steps):
            if step.status == SagaStepStatus.COMPLETED and step.compensation:
                await self._compensate_step(step)
    
    async def _compensate_step(self, step: SagaStep):
        """Compensate a single step"""
        step.status = SagaStepStatus.COMPENSATING
        logger.info(f"Compensating step '{step.name}'")
        
        try:
            # Prepare compensation arguments
            comp_args = step.compensation_args
            comp_kwargs = step.compensation_kwargs.copy()
            
            # Add result data to compensation kwargs if available
            if step.result and step.result.compensation_data:
                comp_kwargs.update(step.result.compensation_data)
            
            # Execute compensation
            if asyncio.iscoroutinefunction(step.compensation):
                await step.compensation(*comp_args, **comp_kwargs)
            else:
                step.compensation(*comp_args, **comp_kwargs)
            
            step.status = SagaStepStatus.COMPENSATED
            step.compensated_at = datetime.now()
            logger.info(f"Step '{step.name}' compensated successfully")
            
        except Exception as e:
            logger.error(f"Compensation failed for step '{step.name}': {e}")
            # Continue with other compensations even if one fails
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed status of the saga transaction"""
        return {
            "transaction_id": self.transaction_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "executed_at": step.executed_at.isoformat() if step.executed_at else None,
                    "compensated_at": step.compensated_at.isoformat() if step.compensated_at else None,
                    "retry_count": step.retry_count,
                    "has_compensation": step.compensation is not None,
                    "result": {
                        "success": step.result.success if step.result else None,
                        "error": step.result.error if step.result else None,
                        "has_data": step.result.data is not None if step.result else False
                    } if step.result else None
                }
                for step in self.steps
            ],
            "context": self.context
        }


class InscriptionSagaOrchestrator:
    """
    Orchestrator for inscription-related saga transactions
    Provides high-level methods for common inscription patterns
    """
    
    def __init__(self, db_session, redis_client=None):
        self.db_session = db_session
        self.redis_client = redis_client
    
    async def create_multi_group_inscription_saga(
        self,
        inscription_data: Dict[str, Any],
        grupos: List[str]
    ) -> SagaTransaction:
        """
        Create a saga for multi-group inscription with proper rollback
        """
        saga = SagaTransaction(name=f"inscription_{inscription_data['registro_academico']}")
        
        # Step 1: Validate student and period
        saga.add_step(
            name="validate_student_and_period",
            action=self._validate_student_and_period,
            action_kwargs={
                "registro_academico": inscription_data["registro_academico"],
                "codigo_periodo": inscription_data["codigo_periodo"]
            }
        )
        
        # Step 2: Reserve grupos (check availability and lock)
        saga.add_step(
            name="reserve_grupos",
            action=self._reserve_grupos,
            compensation=self._release_grupos,
            action_kwargs={"grupos": grupos},
            compensation_kwargs={"grupos": grupos}
        )
        
        # Step 3: Create main inscription record
        saga.add_step(
            name="create_inscription",
            action=self._create_main_inscription,
            compensation=self._delete_inscription,
            action_kwargs=inscription_data
        )
        
        # Step 4: Create inscription details for each group
        for grupo in grupos:
            saga.add_step(
                name=f"create_detail_{grupo}",
                action=self._create_inscription_detail,
                compensation=self._delete_inscription_detail,
                action_kwargs={
                    "codigo_grupo": grupo,
                    "inscription_data": inscription_data
                },
                compensation_kwargs={"codigo_grupo": grupo}
            )
        
        # Step 5: Commit grupo inscriptions (increment counters)
        saga.add_step(
            name="commit_grupo_inscriptions",
            action=self._commit_grupo_inscriptions,
            compensation=self._rollback_grupo_inscriptions,
            action_kwargs={"grupos": grupos}
        )
        
        # Step 6: Send confirmation (optional, non-critical)
        saga.add_step(
            name="send_confirmation",
            action=self._send_inscription_confirmation,
            action_kwargs=inscription_data,
            max_retries=1  # Don't retry too much for non-critical operations
        )
        
        return saga
    
    async def create_single_group_addition_saga(
        self,
        inscription_data: Dict[str, Any],
        grupo: str
    ) -> SagaTransaction:
        """
        Create a saga for adding a single group to existing inscription
        """
        saga = SagaTransaction(name=f"add_group_{grupo}_to_{inscription_data['registro_academico']}")
        
        # Step 1: Validate group availability
        saga.add_step(
            name="validate_group_availability",
            action=self._validate_single_group_availability,
            action_kwargs={
                "grupo": grupo,
                "registro_academico": inscription_data["registro_academico"],
                "codigo_periodo": inscription_data["codigo_periodo"]
            }
        )
        
        # Step 2: Reserve group
        saga.add_step(
            name="reserve_group",
            action=self._reserve_single_group,
            compensation=self._release_single_group,
            action_kwargs={"grupo": grupo},
            compensation_kwargs={"grupo": grupo}
        )
        
        # Step 3: Create inscription detail
        saga.add_step(
            name="create_group_detail",
            action=self._create_inscription_detail,
            compensation=self._delete_inscription_detail,
            action_kwargs={
                "codigo_grupo": grupo,
                "inscription_data": inscription_data
            },
            compensation_kwargs={"codigo_grupo": grupo}
        )
        
        # Step 4: Commit group inscription
        saga.add_step(
            name="commit_group_inscription",
            action=self._commit_single_group_inscription,
            compensation=self._rollback_single_group_inscription,
            action_kwargs={"grupo": grupo}
        )
        
        return saga
    
    # Saga step implementations
    async def _validate_student_and_period(self, registro_academico: str, codigo_periodo: str):
        """Validate student exists and period is active"""
        from app.tasks import _validate_student_and_period_internal
        return await _validate_student_and_period_internal(
            self.db_session, registro_academico, codigo_periodo
        )
    
    async def _reserve_grupos(self, grupos: List[str]) -> Dict[str, Any]:
        """Reserve all grupos for inscription"""
        # This would implement locking mechanism
        reserved_grupos = []
        try:
            for grupo in grupos:
                # Lock grupo in Redis with TTL
                if self.redis_client:
                    lock_key = f"grupo_lock:{grupo}"
                    lock_acquired = self.redis_client.set(lock_key, "locked", ex=300, nx=True)
                    if not lock_acquired:
                        raise Exception(f"Could not acquire lock for grupo {grupo}")
                    reserved_grupos.append(grupo)
            
            return {"reserved_grupos": reserved_grupos, "compensation_data": {"grupos": reserved_grupos}}
        except Exception:
            # Release any locks acquired
            await self._release_grupos(grupos=reserved_grupos)
            raise
    
    async def _release_grupos(self, grupos: List[str]):
        """Release grupo reservations"""
        for grupo in grupos:
            if self.redis_client:
                lock_key = f"grupo_lock:{grupo}"
                self.redis_client.delete(lock_key)
    
    async def _reserve_single_group(self, grupo: str) -> Dict[str, Any]:
        """Reserve a single group"""
        return await self._reserve_grupos([grupo])
    
    async def _release_single_group(self, grupo: str):
        """Release single group reservation"""
        await self._release_grupos([grupo])
    
    async def _validate_single_group_availability(
        self, grupo: str, registro_academico: str, codigo_periodo: str
    ):
        """Validate single group availability including conflicts"""
        from app.tasks import _validate_single_group_internal
        return await _validate_single_group_internal(
            self.db_session, grupo, registro_academico, codigo_periodo
        )
    
    async def _create_main_inscription(self, **inscription_data) -> Dict[str, Any]:
        """Create main inscription record"""
        from app.tasks import _create_main_inscription_internal
        result = await _create_main_inscription_internal(self.db_session, inscription_data)
        return {
            "codigo_inscripcion": result["codigo_inscripcion"],
            "compensation_data": {"codigo_inscripcion": result["codigo_inscripcion"]}
        }
    
    async def _delete_inscription(self, codigo_inscripcion: str):
        """Delete main inscription record"""
        from app.tasks import _delete_inscription_internal
        await _delete_inscription_internal(self.db_session, codigo_inscripcion)
    
    async def _create_inscription_detail(
        self, codigo_grupo: str, inscription_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create inscription detail for a group"""
        from app.tasks import _create_inscription_detail_internal
        result = await _create_inscription_detail_internal(
            self.db_session, codigo_grupo, inscription_data
        )
        return {
            "codigo_detalle": result["codigo_detalle"],
            "compensation_data": {"codigo_detalle": result["codigo_detalle"]}
        }
    
    async def _delete_inscription_detail(self, codigo_detalle: str):
        """Delete inscription detail"""
        from app.tasks import _delete_inscription_detail_internal
        await _delete_inscription_detail_internal(self.db_session, codigo_detalle)
    
    async def _commit_grupo_inscriptions(self, grupos: List[str]):
        """Commit grupo inscriptions (increment counters)"""
        from app.tasks import _commit_grupo_inscriptions_internal
        await _commit_grupo_inscriptions_internal(self.db_session, grupos)
    
    async def _rollback_grupo_inscriptions(self, grupos: List[str]):
        """Rollback grupo inscriptions (decrement counters)"""
        from app.tasks import _rollback_grupo_inscriptions_internal
        await _rollback_grupo_inscriptions_internal(self.db_session, grupos)
    
    async def _commit_single_group_inscription(self, grupo: str):
        """Commit single group inscription"""
        await self._commit_grupo_inscriptions([grupo])
    
    async def _rollback_single_group_inscription(self, grupo: str):
        """Rollback single group inscription"""
        await self._rollback_grupo_inscriptions([grupo])
    
    async def _send_inscription_confirmation(self, **inscription_data):
        """Send inscription confirmation (non-critical)"""
        # This would send email/notification
        logger.info(f"Sending confirmation for inscription {inscription_data.get('codigo_inscripcion')}")
        return {"notification_sent": True}


# Utility functions for saga management
class SagaManager:
    """Global saga manager for tracking and managing saga transactions"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.active_sagas: Dict[str, SagaTransaction] = {}
    
    def register_saga(self, saga: SagaTransaction):
        """Register a saga for tracking"""
        self.active_sagas[saga.transaction_id] = saga
        
        # Store in Redis for persistence
        if self.redis_client:
            saga_data = saga.get_status()
            self.redis_client.setex(
                f"saga:{saga.transaction_id}",
                3600,  # 1 hour TTL
                json.dumps(saga_data, default=str)
            )
    
    def get_saga(self, transaction_id: str) -> Optional[SagaTransaction]:
        """Get saga by transaction ID"""
        return self.active_sagas.get(transaction_id)
    
    def get_all_sagas_status(self) -> List[Dict[str, Any]]:
        """Get status of all active sagas"""
        return [saga.get_status() for saga in self.active_sagas.values()]
    
    async def cleanup_completed_sagas(self):
        """Clean up completed or failed sagas"""
        to_remove = []
        for transaction_id, saga in self.active_sagas.items():
            if saga.status in [SagaStatus.COMPLETED, SagaStatus.COMPENSATED, SagaStatus.FAILED]:
                to_remove.append(transaction_id)
        
        for transaction_id in to_remove:
            del self.active_sagas[transaction_id]
            # Also clean up from Redis
            if self.redis_client:
                self.redis_client.delete(f"saga:{transaction_id}")


# Global saga manager instance
_saga_manager: Optional[SagaManager] = None


def get_saga_manager(redis_client=None) -> SagaManager:
    """Get or create global saga manager"""
    global _saga_manager
    if _saga_manager is None:
        _saga_manager = SagaManager(redis_client)
    return _saga_manager