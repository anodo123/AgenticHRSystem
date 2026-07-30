"""Adapter registry and lookup."""
from app.adapters.attendance_adapter import AttendanceAdapter
from app.adapters.benefits_adapter import BenefitsAdapter
from app.adapters.hris_adapter import HRISAdapter
from app.adapters.leave_adapter import LeaveAdapter
from app.adapters.lms_adapter import LMSAdapter
from app.adapters.payroll_adapter import PayrollAdapter


class AdapterFactory:
    adapters = {
        "HRIS": HRISAdapter(),
        "PAYROLL": PayrollAdapter(),
        "ATTENDANCE": AttendanceAdapter(),
        "LEAVE": LeaveAdapter(),
        "BENEFITS": BenefitsAdapter(),
        "LMS": LMSAdapter(),
    }

    @classmethod
    def get(cls, system: str):
        adapter = cls.adapters.get(system.upper())
        if not adapter:
            raise ValueError(f"Unknown HR adapter: {system}")
        return adapter

    @classmethod
    def health(cls) -> dict:
        return {name: adapter.health_check().data for name, adapter in cls.adapters.items()}
