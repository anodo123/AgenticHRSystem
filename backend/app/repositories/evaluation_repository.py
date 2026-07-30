"""Persistence operations for workflow evaluations."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.evaluation import WorkflowEvaluation


class EvaluationRepository:
    @staticmethod
    def get_by_workflow(db: Session, workflow_id: int) -> Optional[WorkflowEvaluation]:
        return db.query(WorkflowEvaluation).filter(
            WorkflowEvaluation.workflow_id == workflow_id
        ).first()

    @staticmethod
    def upsert(db: Session, workflow_id: int, values: dict) -> WorkflowEvaluation:
        evaluation = EvaluationRepository.get_by_workflow(db, workflow_id)
        if evaluation:
            for key, value in values.items():
                setattr(evaluation, key, value)
        else:
            evaluation = WorkflowEvaluation(workflow_id=workflow_id, **values)
            db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        return evaluation

    @staticmethod
    def list(
        db: Session,
        *,
        skip: int = 0,
        limit: int = 50,
        final_state: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> tuple[int, list[WorkflowEvaluation]]:
        query = db.query(WorkflowEvaluation)
        if final_state:
            query = query.filter(WorkflowEvaluation.final_state == final_state)
        if success is not None:
            query = query.filter(WorkflowEvaluation.success == success)
        return (
            query.count(),
            query.order_by(WorkflowEvaluation.evaluated_at.desc())
            .offset(skip).limit(limit).all(),
        )
