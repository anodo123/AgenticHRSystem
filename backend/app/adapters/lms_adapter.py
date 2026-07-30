"""Deterministic mock learning-management adapter."""
from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult, BaseHRAdapter


class LMSAdapter(BaseHRAdapter):
    system = "LMS"
    records: dict[int, list[dict]] = {}

    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        courses = self.records.setdefault(employee_id, [{
            "course_id": "HR-COMPLIANCE-101",
            "title": "Workplace Compliance",
            "status": "ASSIGNED",
            "completion_percent": 0,
        }])
        return AdapterResult(self.system, True, {"courses": [course.copy() for course in courses]})

    def dry_run(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        course_id = payload.get("course_id")
        course = next((item for item in self.records.setdefault(employee_id, []) if item["course_id"] == course_id), None)
        if not course:
            return AdapterResult(self.system, False, error="LMS course not found")
        updates = payload.get("updates", {})
        invalid = set(updates) - {"status", "completion_percent"}
        if invalid:
            return AdapterResult(self.system, False, error=f"Unsupported LMS fields: {sorted(invalid)}")
        return AdapterResult(self.system, True, {"before": course.copy(), "updates": updates}, dry_run=True)

    def write(self, db: Session, employee_id: int, payload: dict) -> AdapterResult:
        self.read(db, employee_id)
        preview = self.dry_run(db, employee_id, payload)
        if not preview.success:
            return preview
        course = next(item for item in self.records[employee_id] if item["course_id"] == payload["course_id"])
        course.update(preview.data["updates"])
        return self.read(db, employee_id)
