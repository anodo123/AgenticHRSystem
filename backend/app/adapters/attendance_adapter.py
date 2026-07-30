"""Mock attendance adapter."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult, BaseHRAdapter
from app.adapters.utils import model_dict
from app.models.employee import AttendanceRecord


class AttendanceAdapter(BaseHRAdapter):
    system = "ATTENDANCE"
    writable_fields = {"clock_in", "clock_out", "hours_worked", "status", "notes"}
    fields = ("id", "employee_id", "date", "clock_in", "clock_out", "hours_worked", "status", "notes", "updated_at")

    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        query = db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id)
        records = query.order_by(AttendanceRecord.date.desc()).all()
        data = [model_dict(record, self.fields) for record in records]
        return AdapterResult(
            self.system, True, {"records": data, "latest": data[0] if data else None},
            fetched_at=max((record.updated_at for record in records), default=datetime.utcnow()),
        )

    def dry_run(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        record = db.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.id == payload.get("record_id"),
        ).first()
        if not record:
            return AdapterResult(self.system, False, error="Attendance record not found")
        updates = payload.get("updates", {})
        invalid = set(updates) - self.writable_fields
        if invalid:
            return AdapterResult(self.system, False, error=f"Unsupported attendance fields: {sorted(invalid)}")
        return AdapterResult(self.system, True, {"record_id": record.id, "before": model_dict(record, self.fields), "updates": updates}, dry_run=True)

    def write(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        preview = self.dry_run(db, employee_id, payload)
        if not preview.success:
            return preview
        record = db.query(AttendanceRecord).filter(AttendanceRecord.id == preview.data["record_id"]).first()
        for field, value in preview.data["updates"].items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return AdapterResult(self.system, True, {"record": model_dict(record, self.fields)})
