"""Unified facade for controlled HR adapter access."""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.base import AdapterResult
from app.adapters.factory import AdapterFactory
from app.adapters.freshness_gate import FreshnessGate
from app.audit import log_event
from app.models.workflow import IntentCategory
from app.services.workflow_service import WorkflowService


class HRIntegrationService:
    INTENT_SYSTEM = {
        IntentCategory.PAYROLL_ANOMALY: "PAYROLL",
        IntentCategory.ATTENDANCE_ANOMALY: "ATTENDANCE",
        IntentCategory.LEAVE_ANOMALY: "LEAVE",
        IntentCategory.BENEFITS_ANOMALY: "BENEFITS",
        IntentCategory.LMS_ANOMALY: "LMS",
        IntentCategory.DATA_CORRECTION: "HRIS",
    }

    @classmethod
    def system_for(cls, intent: IntentCategory | None, requested: str | None = None) -> str:
        return requested.upper() if requested else cls.INTENT_SYSTEM.get(intent, "HRIS")

    @classmethod
    def fetch_context(
        cls,
        db: Session,
        employee_id: int,
        intent: IntentCategory | None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filters = filters or {}
        systems = ["HRIS"]
        domain = cls.system_for(intent, filters.get("source_system"))
        if domain not in systems:
            systems.append(domain)
        results = {}
        all_fresh = True
        for system in systems:
            adapter = AdapterFactory.get(system)
            initial = adapter.read(db, employee_id, **filters)
            freshness = FreshnessGate.ensure(
                initial,
                lambda value=initial: AdapterResult(
                    value.system, value.success, value.data, error=value.error
                ),
            )
            results[system] = {
                "success": freshness.result.success,
                "data": freshness.result.data,
                "error": freshness.result.error,
                "fetched_at": freshness.result.fetched_at.isoformat(),
                "fresh": freshness.fresh,
                "age_seconds": freshness.age_seconds,
                "refreshed": freshness.refreshed,
            }
            all_fresh = all_fresh and freshness.fresh
        return {"fresh": all_fresh, "domain_system": domain, "systems": results}

    @classmethod
    def execute_action(
        cls,
        db: Session,
        *,
        workflow_id: str,
        workflow_pk: int,
        employee_id: int,
        intent: IntentCategory | None,
        action: dict[str, Any],
        request_data: dict[str, Any],
        actor_id: int | None = None,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        idempotency_key = action["idempotency_key"]
        cached = WorkflowService.check_idempotency(db, idempotency_key)
        if cached:
            return True, None, json.loads(cached["response_body"])

        system = cls.system_for(intent, request_data.get("source_system"))
        adapter = AdapterFactory.get(system)
        action_payload = action.get("payload", {})
        field = action_payload.get("field")
        payload = {
            "record_id": request_data.get("record_id"),
            "course_id": request_data.get("course_id"),
            "updates": {field: action_payload.get("after")} if field else {},
        }
        preview = adapter.dry_run(db, employee_id, payload)
        if not preview.success:
            return False, preview.error, None
        applied = adapter.write(db, employee_id, payload)
        if not applied.success:
            return False, applied.error, None
        response = {
            "system": system,
            "dry_run": preview.data,
            "applied": applied.data,
            "idempotency_key": idempotency_key,
            "verified": True,
        }
        WorkflowService.record_idempotency(
            db, idempotency_key, "POST",
            f"/internal/workflows/{workflow_id}/actions",
            json.dumps(payload, default=str), 200, json.dumps(response, default=str),
        )
        log_event(
            db, event_type="adapter_action_executed", actor_id=actor_id,
            workflow_id=workflow_pk, entity_type="workflow", entity_id=workflow_pk,
            action=f"{system}.write",
            metadata={"idempotency_key": idempotency_key, "verified": True},
        )
        return True, None, response
