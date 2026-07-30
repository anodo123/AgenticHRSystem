"""Deterministic mock benefits provider."""
from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult, BaseHRAdapter


class BenefitsAdapter(BaseHRAdapter):
    system = "BENEFITS"
    records: dict[int, dict] = {}

    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        data = self.records.setdefault(employee_id, {
            "medical_plan": "STANDARD",
            "coverage": "EMPLOYEE",
            "status": "ACTIVE",
            "dependents": 0,
        })
        return AdapterResult(self.system, True, data.copy())

    def dry_run(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        allowed = {"medical_plan", "coverage", "status", "dependents"}
        updates = payload.get("updates", payload)
        invalid = set(updates) - allowed
        if invalid:
            return AdapterResult(self.system, False, error=f"Unsupported benefits fields: {sorted(invalid)}")
        return AdapterResult(self.system, True, {"before": self.read(db, employee_id).data, "updates": updates}, dry_run=True)

    def write(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        preview = self.dry_run(db, employee_id, payload)
        if not preview.success:
            return preview
        self.records.setdefault(employee_id, {}).update(preview.data["updates"])
        return self.read(db, employee_id)
