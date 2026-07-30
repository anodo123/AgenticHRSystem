# Architecture Documentation Index

The original design image is preserved at
[DarwinBoxHLD.jpg](DarwinBoxHLD.jpg). Because it predates parts of the implementation,
the version-controlled Mermaid diagrams and code-derived documents below are the
authoritative description of the current repository:

- [High-Level Design](HLD.md) — context, components, deployment, scaling, reliability
- [Workflow](WORKFLOW.md) — exact states, payroll sequence, approval and failures
- [Data Model](DATA_MODEL.md) — actual SQLAlchemy entities and relationships
- [API Design](API_DESIGN.md) — routes, authentication, schemas, examples
- [Security and Compliance](SECURITY_AND_COMPLIANCE.md) — implemented vs recommended
- [Trade-offs](TRADE_OFFS.md) — design decisions and revisit criteria
- [Demo Guide](DEMO_GUIDE.md) — verified reviewer flow

Current runtime boundaries:

- OpenAI Responses API is a real external integration.
- HRIS/payroll/attendance/leave/benefits/LMS adapters are local simulations.
- PostgreSQL is the system of record and pgvector-compatible store.
- APScheduler runs in the FastAPI process.
- No Redis, message broker, separate worker, notification provider, or production
  identity provider is implemented.
