# Reviewer Demo Guide

This demo exercises authentication, an LLM-backed payroll workflow, human approval,
resume, mutation idempotency, timeline, audit, and evaluation. Allow approximately
10 minutes plus the first Docker build.

## Prerequisites

- Docker Desktop and Docker Compose
- OpenAI Platform API key available only as a runtime environment variable
- PowerShell examples below; replace `$env:` syntax for another shell

## 1. Start and Seed

```powershell
cd <project-root>
$env:OPENAI_API_KEY="<runtime-secret>"
docker compose up --build -d
docker compose ps
```

The backend container runs `python -m scripts.seed_db` before Uvicorn. Wait until:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

Expected readiness: `{"status":"ready","database":"connected"}`.

## 2. Authenticate

Use a seeded employee/requester account from `backend/scripts/seed_db.py`; do not use
production credentials. Example:

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/auth/login `
  -ContentType application/json `
  -Body '{"username":"employee","password":"demo123!"}'
$requesterHeaders = @{ Authorization = "Bearer $($login.access_token)" }
```

Authenticate an `HR_ADMIN` similarly:

```powershell
$admin = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/auth/login `
  -ContentType application/json `
  -Body '{"username":"admin","password":"demo123!"}'
$adminHeaders = @{ Authorization = "Bearer $($admin.access_token)" }
```

## 3. Find a Fictional Seed Employee

```powershell
$employees = Invoke-RestMethod `
  -Uri http://localhost:8000/api/v1/employees/?limit=10 `
  -Headers $requesterHeaders
$employeeId = $employees.items[0].id
```

## 4. Create a High-Risk Payroll Workflow

```powershell
$payload = Get-Content examples/employee_request.json -Raw |
  ConvertFrom-Json
$payload.employee_id = $employeeId
$workflow = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/workflows/ `
  -Headers $requesterHeaders `
  -ContentType application/json `
  -Body ($payload | ConvertTo-Json -Depth 10)
$workflow
```

Expected state: `RECEIVED`.

## 5. Run to Approval

```powershell
$run = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/workflows/$($workflow.workflow_id)/run" `
  -Headers $requesterHeaders
$run.state
$run.approval
```

Expected state: `WAITING_FOR_APPROVAL`, with an `APR-...` ID. This performs real
OpenAI calls. Results depend on the configured model, but deterministic controls keep
the high-risk approval requirement.

## 6. Approve

```powershell
$approvalId = $run.approval.approval_id
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/approvals/$approvalId/approve" `
  -Headers $adminHeaders `
  -ContentType application/json `
  -Body (Get-Content examples/approval_response.json -Raw)
```

Expected approval status: `APPROVED`.

## 7. Resume and Verify

```powershell
$completed = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/workflows/$($workflow.workflow_id)/run" `
  -Headers $requesterHeaders
$completed.state
```

Expected state: `COMPLETED`. The adapter performs dry-run and an allow-listed local
database write, then persists an idempotency result.

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/workflows/$($workflow.workflow_id)/timeline" `
  -Headers $requesterHeaders

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/evaluations/$($workflow.workflow_id)" `
  -Headers $adminHeaders

Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/audit/?limit=50" `
  -Headers $adminHeaders
```

Inspect the transition sequence, five agent outputs/evidence, approval decision,
adapter action event, and evaluation.

## Optional UI

Open `http://localhost:3000`, sign in, then use Workflows, Approvals, Audit, and
Dashboard. The UI supports create/detail/timeline/pause/resume/cancel and approval
decisions.

## Cleanup

```powershell
docker compose down
```

To delete all demo database data:

```powershell
docker compose down -v
```

The `-v` command is destructive and removes the PostgreSQL volume.

## Troubleshooting

- `/ready` 503 with `OPENAI_API_KEY_not_configured`: set the runtime variable and
  recreate the backend container.
- Workflow `FAILED`: inspect workflow `error_message`, backend logs, and audit events.
- Approval 403: use a user with the current required role.
- Mutation fails with “record not found”: use a seeded employee with a payroll record.
- Repeating an already resolved approval is expected to fail; duplicate execution is
  prevented by approval status and adapter idempotency.
