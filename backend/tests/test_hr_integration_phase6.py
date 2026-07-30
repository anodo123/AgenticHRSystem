"""Integration tests for adapter-backed workflow execution."""
from datetime import datetime, timedelta

from app.models.audit import AuditLog
from app.models.employee import Employee, EmployeeType, EmploymentStatus, PayrollRecord
from app.models.workflow import IntentCategory, TriggerType
from app.services.agent_orchestration import AgentOrchestrationService
from app.services.approval_service import ApprovalService
from app.services.hr_integration_service import HRIntegrationService
from app.services.workflow_service import WorkflowService


def payroll_employee(db):
    employee = Employee(
        employee_number="EMP-WF",
        first_name="Workflow",
        last_name="Employee",
        email="workflow.employee@example.com",
        department="Finance",
        legal_entity="ACME",
        country="IN",
        role="Analyst",
        employment_status=EmploymentStatus.ACTIVE,
        employee_type=EmployeeType.FULL_TIME,
        hire_date=datetime.utcnow() - timedelta(days=100),
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
    db.add(payroll)
    db.commit()
    return employee, payroll


def test_fetch_context_selects_domain_adapter(db):
    employee, _ = payroll_employee(db)
    context = HRIntegrationService.fetch_context(
        db, employee.id, IntentCategory.PAYROLL_ANOMALY,
    )
    assert context["fresh"]
    assert context["domain_system"] == "PAYROLL"
    assert set(context["systems"]) == {"HRIS", "PAYROLL"}


def test_workflow_reads_adapter_and_executes_idempotent_correction(db, users):
    employee, payroll = payroll_employee(db)
    workflow_id = WorkflowService.create_workflow(
        db,
        TriggerType.EMPLOYEE_REQUEST,
        users[0].id,
        employee.id,
        "Payroll net salary discrepancy",
        {
            "field": "net_salary",
            "expected_value": 9500,
            "risk_level": "LOW",
            "source_system": "PAYROLL",
        },
    )["workflow_id"]
    success, error, result = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert result["state"] == "COMPLETED"
    investigation = result["agent_outputs"]["anomaly_investigation"]
    assert investigation["observed_value"] == 9000
    assert investigation["adapter_context_used"]
    execution = result["agent_outputs"]["adapter_execution"]
    assert execution["system"] == "PAYROLL"
    assert execution["verified"]
    db.refresh(payroll)
    assert float(payroll.net_salary) == 9500
    assert db.query(AuditLog).filter(
        AuditLog.event_type == "adapter_action_executed"
    ).count() == 1
    action = result["agent_outputs"]["action"]
    repeated = HRIntegrationService.execute_action(
        db,
        workflow_id=workflow_id,
        workflow_pk=1,
        employee_id=employee.id,
        intent=IntentCategory.PAYROLL_ANOMALY,
        action=action,
        request_data={"source_system": "PAYROLL"},
    )
    assert repeated[0] and repeated[2]["idempotency_key"] == execution["idempotency_key"]
    assert db.query(AuditLog).filter(
        AuditLog.event_type == "adapter_action_executed"
    ).count() == 1


def test_approved_workflow_executes_adapter_after_resume(db, users):
    employee, payroll = payroll_employee(db)
    workflow_id = WorkflowService.create_workflow(
        db,
        TriggerType.EMPLOYEE_REQUEST,
        users[0].id,
        employee.id,
        "High risk payroll net salary correction",
        {
            "field": "net_salary",
            "expected_value": 9750,
            "risk_level": "HIGH",
            "source_system": "PAYROLL",
        },
    )["workflow_id"]
    success, error, waiting = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert waiting["state"] == "WAITING_FOR_APPROVAL"
    success, error, _ = ApprovalService.decide(
        db,
        approval_id=waiting["approval"]["approval_id"],
        approver=users[1],
        approve=True,
    )
    assert success, error
    success, error, completed = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert completed["state"] == "COMPLETED"
    assert completed["agent_outputs"]["adapter_execution"]["verified"]
    db.refresh(payroll)
    assert float(payroll.net_salary) == 9750
