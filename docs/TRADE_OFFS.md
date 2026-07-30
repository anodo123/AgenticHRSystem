# Architecture Decisions and Trade-offs

## Multi-agent rather than one prompt

**Context:** Classification, evidence, policy, action, and compliance have different
responsibilities and audit needs.  
**Selected Approach:** Five ordered agents with persisted outputs.  
**Alternatives Considered:** One large prompt; dynamic agent hand-offs.  
**Benefits:** Inspectable boundaries, focused schemas, isolated testing.  
**Limitations:** Five calls add latency/cost; orchestration is fixed.  
**Revisit:** When evals show fewer calls preserve quality, or workflows need dynamic graphs.

## Agents only for reasoning

**Context:** State, permissions, approvals, scheduling, and writes must be predictable.  
**Selected Approach:** LLMs reason; normal services enforce and mutate.  
**Alternatives Considered:** Agent tools controlling the full lifecycle.  
**Benefits:** Auditability, deterministic tests, reduced blast radius.  
**Limitations:** More explicit code and less autonomous flexibility.  
**Revisit:** Tool use may expand only behind independent authorization and schemas.

## Persisted explicit state machine

**Context:** Human approval may pause execution for hours.  
**Selected Approach:** Workflow row plus transition/execution/evidence history.  
**Alternatives Considered:** In-memory chain; external workflow engine.  
**Benefits:** Resume, visibility, validation, recovery.  
**Limitations:** Hand-maintained transitions and transaction boundaries.  
**Revisit:** Adopt Temporal/Camunda when distributed long-running workflows dominate.

## PostgreSQL as system of record

**Context:** Workflows, HR data, approvals, audit, and policy metadata are relational.  
**Selected Approach:** PostgreSQL plus pgvector-compatible columns.  
**Alternatives Considered:** Document DB and separate vector database.  
**Benefits:** Transactions, mature indexing, fewer operational systems.  
**Limitations:** Current vector scoring is in application memory.  
**Revisit:** Use native pgvector ANN first; separate vector service only at scale.

## Compliance constraints plus LLM explanation

**Context:** A model must not downgrade a sensitive control.  
**Selected Approach:** Model returns structured decision/explanation; deterministic
risk, violation, conflict, role, and authorization fields remain authoritative.  
**Alternatives Considered:** Pure rules; pure LLM policy decision.  
**Benefits:** Explainability with enforceable invariants.  
**Limitations:** Rules are simplified request flags, not a legal policy engine.  
**Revisit:** Introduce versioned rules/decision tables owned by compliance teams.

## Separate compliance and approval

**Context:** Human consent cannot legitimize a prohibited action.  
**Selected Approach:** Compliance routes first; approval exists only for permissible
sensitive actions.  
**Alternatives Considered:** Send every risky decision to a manager.  
**Benefits:** Clear governance and fewer inappropriate approvals.  
**Limitations:** Requires accurate policy/risk classification.  
**Revisit:** Add exception/escalation case management, never a direct denial override.

## Synchronous orchestration

**Context:** Interview implementation benefits from simple request/response execution.  
**Selected Approach:** `/run` performs the agent chain synchronously.  
**Alternatives Considered:** Celery, Kafka, durable workflow engine.  
**Benefits:** Easy local setup and deterministic API tests.  
**Limitations:** LLM latency occupies API workers; client retries can complicate runs.  
**Revisit:** Move each step to leased queue jobs for production.

## In-process task scheduler

**Context:** Scheduled scans need cron, priority, and retries without extra infrastructure.  
**Selected Approach:** APScheduler in FastAPI lifespan; due tasks/runs persisted.  
**Alternatives Considered:** Celery Beat, Kubernetes CronJobs, managed scheduler.  
**Benefits:** Minimal deployment, durable task definitions.  
**Limitations:** Multiple API replicas may duplicate dispatch; fallback scheduler is
non-executing.  
**Revisit:** Dedicated singleton scheduler plus distributed workers.

## Local hashed embeddings

**Context:** The project needs deterministic offline RAG tests and pgvector portability.  
**Selected Approach:** Stable hashed-token 128-dimensional vectors cached in DB.  
**Alternatives Considered:** Hosted embedding API; lexical search.  
**Benefits:** No embedding cost/network and reproducible tests.  
**Limitations:** Weak semantic quality; application-side scan.  
**Revisit:** Governed embedding model and ANN index after retrieval evaluation.

## Sanitized episodic memory

**Context:** Resolved incidents can improve future investigation.  
**Selected Approach:** Regex-sanitized incident summaries and similarity retrieval.  
**Alternatives Considered:** Raw transcripts; no memory.  
**Benefits:** Reusable context with basic PII reduction.  
**Limitations:** Regex redaction is incomplete and memory has no retention policy.  
**Revisit:** DLP classification, consent, TTL, tenant scope, and quality feedback.

## Strict structured outputs

**Context:** Downstream state and action code cannot parse arbitrary prose safely.  
**Selected Approach:** Responses API JSON schema plus post-model validation/overwrites.  
**Alternatives Considered:** JSON prompting and parser repair.  
**Benefits:** Fail-closed contract and simpler persistence.  
**Limitations:** Schema/model compatibility and evolution overhead.  
**Revisit:** Version schemas and add compatibility migrations as agent outputs evolve.
