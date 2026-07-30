# Security and Compliance

This document separates controls present in the repository from controls required
for a production HR platform.

## Implemented Controls

### Authentication and Authorization

- Signed access and refresh JWTs with expiry and token type
- Active-user check on authenticated requests
- Roles and permissions persisted through many-to-many mappings
- Superuser override plus permission/role dependencies
- Workflow owner checks for read/mutation routes
- Required-role, delegation, expiry, and status checks for approvals
- Task management restricted to admin roles/permission
- Employee creation/update and audit routes use permission dependencies

### Workflow and Action Safety

- Explicit valid transition graph; terminal and paused workflow checks
- Optimistic workflow version update
- Compliance constraints preserve risk/policy decisions after LLM output
- Non-compliant actions terminate as `DENIED`; approval cannot override denial
- High/critical mutation risk requires approval by default
- Adapter writes are allow-listed, employee-scoped, and dry-run first
- Action digest produces persisted idempotency keys
- No public integration write endpoint
- Strict JSON-schema LLM outputs and fail-closed parsing/refusal handling

### Traceability and Data Handling

- Transitions, executions, evidence, compliance, approvals, adapter actions, and task
  runs are persisted
- Correlation ID on requests and JSON logs
- Per-entity hash-linked audit events
- Policy citations preserve policy/chunk/version metadata
- Incident memory applies regex redaction for emails, employee IDs, and long numbers
- OpenAI credentials come from runtime environment; no key is committed
- API rate limiting exists, but is process-local

## Compliance Decision Examples

These examples reflect current code behavior, not universal HR policy.

| Proposed action | Current compliance result | Approval | Code-based reason |
|---|---|---|---|
| Policy query or no mutation | `ALLOW` | No | Action type is `NO_ACTION` |
| Low/medium-risk record correction | `ALLOW` | No | No conflict/violation and risk below high |
| High-risk payroll correction | `REQUIRE_APPROVAL` | Yes, default `HR_ADMIN` | Risk is `HIGH`/`CRITICAL` |
| Request with `policy_violation` flag | `DENY` | Not applicable | Explicit violation constraint |
| Conflicting policy decisions | `ESCALATE` | Not applicable | Policy conflict flag |
| Explicit configured compliance decision | Supplied valid enum | Depends on decision | Test/demo control in request data |

The system does not currently implement field-level rules such as “only view your own
salary.” Employee read endpoints require authentication but are not ownership-scoped.
That must be fixed before production.

## Threat and Control Review

| Area | Current state | Production recommendation |
|---|---|---|
| Identity | Local username/password JWT | Enterprise OIDC/SAML, MFA, token revocation |
| RBAC | Roles, permissions, owner checks | Tenant-aware ABAC and segregation of duties |
| Employee isolation | Workflow owner checks | Employee/manager/HR scope on every HR data route |
| Salary access | Authenticated employee endpoint may expose salary | Field-level permission, masking, access-purpose logging |
| PII masking | Incident regex sanitization only | Typed data classification and redaction before logs/LLM |
| Prompt injection | Structured schemas and immutable citations/payloads | Input screening, content boundaries, trusted tool policy |
| Policy trust | Metadata/checksum fields and citations | Signed publishing, reviewer approval, source ACLs |
| LLM leakage | Runtime key and bounded structured call | Region/vendor controls, DPA, redaction, no-retention setting |
| Secrets | Environment-based | Secret manager/KMS, rotation, workload identity |
| Encryption | HTTPS endpoint assumed; DB config does not enforce TLS | TLS/mTLS, encrypted volumes/columns, KMS envelopes |
| Audit | Database hash links | Append-only external store, anchor/sign hashes, retention |
| Data retention | No automated retention | Policy-specific TTL, legal hold, deletion workflows |
| Regional rules | Country is policy/employee metadata | Residency partitions and regional processing controls |
| Rate limiting | In-memory client window | Distributed gateway/Redis limiter |

## Prompt Injection and Agent Boundaries

Request summaries and retrieved policy text are untrusted input. The current system
limits impact by requiring strict output schemas and by overwriting model-controlled
fields with deterministic facts: policy citations, discrepancy calculations, action
payload/idempotency, and compliance control fields. The model cannot directly call an
adapter.

Production should additionally:

1. label policy/request content as data, not instructions;
2. reject or quarantine prompt-injection indicators;
3. authorize every tool argument independently;
4. redact sensitive fields before the model boundary;
5. log response IDs/token usage without raw sensitive prompts;
6. evaluate model/prompt changes against adversarial datasets.

## Approval Security

Approval is tied to a persisted workflow in `WAITING_FOR_APPROVAL`. The service checks
status, expiry, workflow state, required current role/delegate, and active target
before changing state. Multi-level decisions are immutable. Requesters cannot
self-approve unless they independently hold the required role or are superuser.

Production separation-of-duty rules should explicitly forbid requester/approver
identity overlap for selected action classes, require step-up authentication, and sign
approval links or callbacks.

## Audit Caveat

Audit rows are append-only by convention, not database policy. Hash chaining is
entity-local and the hash is calculated from the optional current-state payload, which
is frequently empty. The implementation demonstrates reconstruction intent but should
not be represented as a regulatory-grade immutable ledger.
