"""Mock leave-management adapter."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult, BaseHRAdapter
from app.adapters.utils import model_dict
from app.models.employee import LeaveRequest


class LeaveAdapter(BaseHRAdapter):
    system = "LEAVE"
    writable_fields = {"status", "manager_notes"}
    fields = ("id", "employee_id", "leave_type", "start_date", "end_date", "days_requested", "status", "reason", "manager_notes", "updated_at")

    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        records = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee_id
        ).order_by(LeaveRequest.start_date.desc()).all()
        data = [model_dict(record, self.fields) for record in records]
        approved = sum(float(record.days_requested) for record in records if record.status == "APPROVED")
        return AdapterResult(
            self.system, True,
            {"requests": data, "approved_days": approved, "mock_annual_balance": max(0, 20 - approved)},
            fetched_at=max((record.updated_at for record in records), default=datetime.utcnow()),
        )

    def dry_run(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        record = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.id == payload.get("record_id"),
        ).first()
        if not record:
            return AdapterResult(self.system, False, error="Leave request not found")
        updates = payload.get("updates", {})
        invalid = set(updates) - self.writable_fields
        if invalid:
            return AdapterResult(self.system, False, error=f"Unsupported leave fields: {sorted(invalid)}")
        return AdapterResult(self.system, True, {"record_id": record.id, "before": model_dict(record, self.fields), "updates": updates}, dry_run=True)

    def write(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        preview = self.dry_run(db, employee_id, payload)
        if not preview.success:
            return preview
        record = db.query(LeaveRequest).filter(LeaveRequest.id == preview.data["record_id"]).first()
        for field, value in preview.data["updates"].items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return AdapterResult(self.system, True, {"record": model_dict(record, self.fields)})
