# Postman end-to-end demo

Import `AgenticHRSystem.postman_collection.json` into Postman and run the whole
collection in its saved order.

## Prerequisites

From the project root, start the Docker stack with a real runtime OpenAI key:

```powershell
$env:OPENAI_API_KEY="<your-runtime-key>"
docker compose up --build -d
docker compose ps
```

The collection uses collection-scoped variables, so no separate Postman environment
file is required. Its default API URL is `http://localhost:8000`.

## Automated scenario

1. Check liveness and readiness.
2. Log in as the seeded `employee` and `admin` users.
3. Insert a uniquely numbered demo employee.
4. Insert and retrieve a data-correction policy.
5. Create a high-risk department-correction workflow for the inserted employee.
6. Run the agent chain until it reaches the human approval gate.
7. Capture the generated approval ID and approve it as `HR_ADMIN`.
8. Resume the workflow and execute the approved HRIS mutation.
9. Verify the updated employee, workflow timeline, audit events, and incident memory.

Each run generates unique employee and policy identifiers. The demo intentionally
persists its inserted records. To reset all Docker database data:

```powershell
docker compose down -v
```
