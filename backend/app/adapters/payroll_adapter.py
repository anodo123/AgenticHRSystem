"""Mock payroll adapter backed by payroll records."""
from datetime import datetime
from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult, BaseHRAdapter
from app.adapters.utils import model_dict
from app.models.employee import PayrollRecord


class PayrollAdapter(BaseHRAdapter):
    system = "PAYROLL"
    writable_fields = {"gross_salary", "overtime_amount", "deductions", "net_salary", "status", "notes"}
    fields = (
        "id", "employee_id", "payroll_period", "gross_salary", "overtime_amount",
        "deductions", "net_salary", "status", "notes", "updated_at",
    )

    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        query = db.query(PayrollRecord).filter(PayrollRecord.employee_id == employee_id)
        if filters.get("payroll_period"):
            query = query.filter(PayrollRecord.payroll_period == filters["payroll_period"])
        records = query.order_by(PayrollRecord.payroll_period.desc()).all()
        data = [model_dict(record, self.fields) for record in records]
        fetched_at = max((record.updated_at for record in records), default=None)
        return AdapterResult(
            self.system, True, {"records": data, "latest": data[0] if data else None},
            fetched_at=fetched_at or datetime.utcnow(),
        )

    def dry_run(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        record_id = payload.get("record_id")
        record = db.query(PayrollRecord).filter(
            PayrollRecord.employee_id == employee_id,
            PayrollRecord.id == record_id,
        ).first() if record_id else db.query(PayrollRecord).filter(
            PayrollRecord.employee_id == employee_id
        ).order_by(PayrollRecord.payroll_period.desc()).first()
        if not record:
            return AdapterResult(self.system, False, error="Payroll record not found")
        updates = payload.get("updates", {})
        invalid = set(updates) - self.writable_fields
        if invalid:
            return AdapterResult(self.system, False, error=f"Unsupported payroll fields: {sorted(invalid)}")
        return AdapterResult(
            self.system, True,
            {"record_id": record.id, "before": model_dict(record, self.fields), "updates": updates},
            dry_run=True,
        )

    def write(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        preview = self.dry_run(db, employee_id, payload)
        if not preview.success:
            return preview
        record = db.query(PayrollRecord).filter(
            PayrollRecord.id == preview.data["record_id"]
        ).first()
        for field, value in preview.data["updates"].items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return AdapterResult(self.system, True, {"record": model_dict(record, self.fields)})
