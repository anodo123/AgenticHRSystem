"""Unit tests for Phase 6 mock HR adapters and freshness gate."""
from datetime import datetime, timedelta

from app.adapters.base import AdapterResult
from app.adapters.factory import AdapterFactory
from app.adapters.freshness_gate import FreshnessGate
from app.models.employee import (
    AttendanceRecord,
    Employee,
    EmployeeType,
    EmploymentStatus,
    LeaveRequest,
    PayrollRecord,
)


def employee_records(db):
    employee = Employee(
        employee_number="EMP-ADAPTER",
        first_name="Adapter",
        last_name="Test",
        email="adapter@example.com",
        department="Finance",
        legal_entity="ACME",
        country="IN",
        role="Analyst",
        employment_status=EmploymentStatus.ACTIVE,
        employee_type=EmployeeType.FULL_TIME,
        hire_date=datetime.utcnow() - timedelta(days=365),
        salary=120000,
        data_sync_timestamp=datetime.utcnow(),
    )
    db.add(employee)
    db.commit()
    payroll = PayrollRecord(
        employee_id=employee.id,
        payroll_period="2026-07",
        gross_salary=10000,
        overtime_amount=0,
        deductions=1000,
        net_salary=9000,
        status="PROCESSED",
    )
    attendance = AttendanceRecord(
        employee_id=employee.id,
        date=datetime.utcnow(),
        hours_worked=7,
        status="PARTIAL",
    )
    leave = LeaveRequest(
        employee_id=employee.id,
        leave_type="ANNUAL",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=1),
        days_requested=1,
        status="PENDING",
    )
    db.add_all([payroll, attendance, leave])
    db.commit()
    return employee, payroll, attendance, leave


def test_all_adapters_health_and_reads(db):
    employee, _, _, _ = employee_records(db)
    health = AdapterFactory.health()
    assert set(health) == {"HRIS", "PAYROLL", "ATTENDANCE", "LEAVE", "BENEFITS", "LMS"}
    for system in health:
        result = AdapterFactory.get(system).read(db, employee.id)
        assert result.success, (system, result.error)


def test_controlled_payroll_dry_run_and_write(db):
    employee, payroll, _, _ = employee_records(db)
    adapter = AdapterFactory.get("PAYROLL")
    payload = {"record_id": payroll.id, "updates": {"net_salary": 9500}}
    preview = adapter.dry_run(db, employee.id, payload)
    assert preview.success and preview.dry_run
    assert float(payroll.net_salary) == 9000
    applied = adapter.write(db, employee.id, payload)
    assert applied.success
    assert applied.data["record"]["net_salary"] == 9500
    rejected = adapter.dry_run(
        db, employee.id, {"record_id": payroll.id, "updates": {"bank_account": "x"}},
    )
    assert not rejected.success


def test_attendance_leave_benefits_and_lms_mutations(db):
    employee, _, attendance, leave = employee_records(db)
    attendance_result = AdapterFactory.get("ATTENDANCE").write(
        db, employee.id,
        {"record_id": attendance.id, "updates": {"hours_worked": 8, "status": "PRESENT"}},
    )
    assert attendance_result.success
    leave_result = AdapterFactory.get("LEAVE").write(
        db, employee.id,
        {"record_id": leave.id, "updates": {"status": "APPROVED"}},
    )
    assert leave_result.success
    benefits = AdapterFactory.get("BENEFITS").write(
        db, employee.id, {"updates": {"coverage": "FAMILY", "dependents": 2}},
    )
    assert benefits.data["coverage"] == "FAMILY"
    lms = AdapterFactory.get("LMS")
    lms.read(db, employee.id)
    course = lms.write(db, employee.id, {
        "course_id": "HR-COMPLIANCE-101",
        "updates": {"status": "COMPLETED", "completion_percent": 100},
    })
    assert course.data["courses"][0]["status"] == "COMPLETED"


def test_freshness_gate_refreshes_stale_result():
    stale = AdapterResult(
        "TEST", True, {"value": 1},
        fetched_at=datetime.utcnow() - timedelta(hours=2),
    )
    checked = FreshnessGate.ensure(
        stale, lambda: AdapterResult("TEST", True, {"value": 2}),
        max_age_minutes=30,
    )
    assert checked.fresh and checked.refreshed
    assert checked.result.data["value"] == 2
