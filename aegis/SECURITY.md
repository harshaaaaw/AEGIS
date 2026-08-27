# AEGIS Security Model

## Trust boundaries
- **Tenant isolation**: every run, verdict, and memory record is scoped by
  `tenant_id`. Verdict verification is tenant-scoped; a tenant cannot read
  another tenant's verdict (see `gate.verify_verdict(tenant_id=...)`).
- **Untrusted input**: agent tool results are treated as untrusted. The
  agent-sentinel shield inspects every `TOOL_CALL` output; adversarial content
  (prompt injection, markdown exfil, secrets) blocks the gate.
- **Externalized state**: no agent evidence lives in process memory. The Audit
  Spine (SQLite), run-replay store (JSONL), and verdict ledger (JSONL) are the
  system of record; processes are cattle.

## Cryptographic guarantees
- **Signed verdicts**: HMAC-SHA256 over a canonical decision payload. Tampering
  with a stored verdict is detectable via `verify_verdict`.
- **Hash-chained ledger**: each verdict line carries `prev_hash` (SHA-256 of the
  prior line). Editing any historical verdict breaks the chain from that point
  forward — full ledger integrity is checked on every verify.
- **Secret policy**: signing secrets must be >= 32 bytes (RFC 7518 §3.2). The
  app refuses to boot with a weak secret (`security.require_strong_secret`).

## Network
- **SSRF guard** (`security.is_ssrf_safe`): resolves the URL host via DNS and
  blocks any address in link-local / metadata (169.254.0.0/16), loopback,
  RFC1918, or ULA ranges. Cloud metadata endpoints are unreachable by design.
- **Kubernetes**: NetworkPolicy restricts egress to redis/postgres/OTel only;
  `automountServiceAccountToken: false`; gVisor/Kata sandbox sidecar for
  untrusted tool execution.

## Abuse resistance
- **Rate limiting**: slowapi limits on `/api/v1/runs` (20/min) and
  `/api/v1/gate/evaluate` (10/min) per source IP (OWASP LLM ATC-8 / A10).
- **Graduated trust**: agents start in `shadow` tier; no day-one production
  autonomy. Promotion requires explicit, reviewed steps; incidents demote.

## Supply chain
- **SAST**: `bandit` — no issues identified (run `bandit -r aegis/src/aegis`).
- **SCA**: `pip-audit` — no known vulnerabilities in the dependency tree.
- CI blocks merges on any anti-slop P1 hit (bare-except, invented APIs) or gate
  regression.

## Known limitations (honest)
- The in-process event bus is for a single control-plane instance; multi-replica
  fan-out would use the Redis/Kafka backplane (wired in deploy, not in-process).
- evalforge golden-set evaluation currently uses a documented stand-in pipeline;
  wire a real candidate pipeline before relying on it for ship decisions.
- Causal Decisions uses OLS on provided data; it is an estimator, not a
  randomized experiment — reported with a confidence interval, not a point claim.
