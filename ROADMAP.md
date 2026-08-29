# AEGIS Roadmap

A living plan. We ship the control plane in thin, verifiable slices. Each item below is a tested subsystem plus a line in the audit Spine.

## Now - 0.1.0 (shipped)

- [x] Ship Gate - replay plus shield plus eval into a signed verdict with hash chained ledger
- [x] Causal Decisions - OLS effect estimator with honest confidence intervals
- [x] Spine - SQLite tamper evident store with idempotent run ids and tenant scope
- [x] Event bus with per subscriber failure isolation
- [x] CLI - `certify`, `verify`, `drift`, `posture`, `ssrf`, `server` - zero config, no K8s needed
- [x] HTTP API - FastAPI with JWT auth, rate limiting, OTel metrics
- [x] Quality gate - ruff plus mypy plus bandit plus pytest in CI

## Next - 0.2.0 (in design)

- [ ] SwapWatch - statistical drift test (Cohen d, Welch t test, BH correction) over live vs certified outputs
- [ ] Governed Memory - Neo4j backed graph with ABAC read scopes and provenance
- [ ] Contract Intel - OCR plus NER clause classifier over vendor PDFs with spend benchmark

## Later - 0.3.0

- [ ] Twin Truth - live fidelity drift scoring against telemetry (Kafka or Flink ingest)
- [ ] Sim/RL Factory - turns real workflows into RL environments and golden traces, feeds Ship Gate
- [ ] Autonomous Ops - KEDA scaled claims execution and coordination workers

## Platform

- [ ] Helm chart with OIDC, Postgres plus pgvector plus Neo4j, and S3 audit backend
- [ ] Multi replica bus via Redis or Kafka backplane
- [ ] Role panes - CISO, CFO, CTO, Compliance, Ops dashboards on one Spine

---

Have a use case that should shape the order? Open an issue with `[ROADMAP]` in the title. We prioritize by real user evidence.
