"""Mock HRIS adapter backed by employee records."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult, BaseHRAdapter
from app.adapters.utils import model_dict
from app.models.employee import Employee


class HRISAdapter(BaseHRAdapter):
    system = "HRIS"
    writable_fields = {"department", "business_unit", "role", "manager_id", "employment_status"}
    fields = (
        "id", "employee_number", "first_name", "last_name", "department",
        "business_unit", "legal_entity", "country", "manager_id", "role",
        "employment_status", "employee_type", "hire_date", "salary", "currency",
        "data_sync_timestamp",
    )

    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            return AdapterResult(self.system, False, error="Employee not found")
        data = model_dict(employee, self.fields)
        data["direct_report_ids"] = [item.id for item in employee.direct_reports]
        return AdapterResult(
            self.system, True, data,
            fetched_at=employee.data_sync_timestamp or employee.updated_at,
        )

    def dry_run(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        current = self.read(db, employee_id)
        if not current.success:
            return current
        updates = payload.get("updates", payload)
        invalid = set(updates) - self.writable_fields
        if invalid:
            return AdapterResult(self.system, False, error=f"Unsupported HRIS fields: {sorted(invalid)}")
        return AdapterResult(
            self.system, True,
            {"before": current.data, "updates": updates}, dry_run=True,
        )

    def write(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        preview = self.dry_run(db, employee_id, payload)
        if not preview.success:
            return preview
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        for field, value in preview.data["updates"].items():
            setattr(employee, field, value)
        employee.data_sync_timestamp = datetime.utcnow()
        db.commit()
        db.refresh(employee)
        return self.read(db, employee_id)
