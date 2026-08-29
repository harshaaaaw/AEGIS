# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (master) | Yes - active development |

As a pre 1.0 project we support only the latest master. Pin to a commit hash for production use until we tag 1.0.

## Reporting a vulnerability

Do not open a public GitHub issue for security vulnerabilities.

Email the maintainer privately: open an issue with title `[SECURITY] private disclosure` and we will provide a private channel, or use GitHub private vulnerability reporting:

GitHub repo -> Security -> Report a vulnerability

We will acknowledge within 48 hours and provide a fix timeline. We follow coordinated disclosure: you report privately, we fix and release, then we publish an advisory and credit you if you wish.

## Trust boundaries

- **Tenant isolation**: every run, verdict, and memory record is scoped by `tenant_id`. Verdict verification is tenant scoped. A tenant cannot read another tenant verdict.
- **Untrusted input**: agent tool results are treated as untrusted. The agent-sentinel shield inspects every `TOOL_CALL` output. Injection, exfil, or secret leak blocks the gate.
- **Externalized state**: no agent evidence lives in process memory. The Audit Spine (SQLite), run replay store (JSONL), and verdict ledger (JSONL) are the system of record.

## Cryptographic guarantees

- **Signed verdicts**: HMAC SHA256 over a canonical decision payload. Tampering is detectable via `verify_verdict`.
- **Hash chained ledger**: each verdict line carries `prev_hash` (SHA256 of the prior line). Editing any historical verdict breaks the chain.
- **Secret policy**: signing secrets must be 32 bytes or more (RFC 7518). The app refuses to boot with a weak secret.

## Network

- **SSRF guard** (`security.is_ssrf_safe`): resolves the URL host via DNS and blocks link local, loopback, RFC1918, and ULA ranges. Cloud metadata endpoints are unreachable.
- **Kubernetes**: NetworkPolicy restricts egress to redis, postgres, OTel only. `automountServiceAccountToken: false`. Sandbox sidecar for untrusted tool execution.

## Abuse resistance

- **Rate limiting**: slowapi limits on `/api/v1/runs` (20 per min) and `/api/v1/gate/evaluate` (10 per min) per IP.
- **Graduated trust**: agents start in `shadow` tier. No day one production autonomy. Promotion requires review, incidents demote.

## Supply chain

- **SAST**: `bandit -r aegis/src/aegis` - no issues identified
- **SCA**: `pip-audit` - no known vulnerabilities in the dependency tree
- CI blocks merges on any high severity bandit finding or gate regression

## Known limitations

- The in process event bus is for a single control plane instance. Multi replica fan out would use the Redis or Kafka backplane (wired in deploy, not in process).
- evalforge golden set evaluation currently uses a documented stand in pipeline. Wire a real candidate pipeline before relying on it for ship decisions.
- Causal Decisions uses OLS on provided data. It is an estimator, not a randomized experiment, reported with a confidence interval.
