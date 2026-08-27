"""The Sentinel: per-turn shield with an enforced latency budget.

Contract: inspect_user_input / inspect_tool_result / inspect_outbound
return a Decision in under `latency_budget_us` microseconds of scanning
work (p99 across the benchmark suite). If a scan would exceed the
budget, the shield degrades safely: the content is treated as BLOCK for
untrusted lanes (fail closed) and labeled LATENCY_BUDGET_BREACH.

Labels are stable strings meant to be piped into eval datasets,
fine-tune sets, or RL reward terms. The audit log is hash-chained per
tenant so an operator can prove later exactly what was blocked and why.
"""

from __future__ import annotations

import os

from .audit import AuditLog
from .breaker import BreakerConfig, CircuitBreaker
from .models import (
    Action, Channel, Decision, Label, ScanReport, Severity,
    ToolCall, ToolResult, TurnContext, now_us,
)
from . import rules


class LatencyBudgetExceeded(RuntimeError):
    pass


class Sentinel:
    def __init__(
        self,
        audit_root: str | os.PathLike = ".sentinel",
        latency_budget_us: float = 10_000.0,   # enforced per-scan budget (9x under the 90ms industry classifier target; measured p50s in README)
        block_on: set[Severity] | None = None,
        redact_on: set[Severity] | None = None,
        breaker_cfg: BreakerConfig | None = None,
    ):
        self.audit = AuditLog(os.path.join(audit_root, "audit"))
        self.latency_budget_us = latency_budget_us
        self.block_on = block_on or {Severity.CRITICAL}
        self.redact_on = redact_on or {Severity.MEDIUM, Severity.HIGH}
        self.breaker = CircuitBreaker(breaker_cfg)

    # ---- public lanes --------------------------------------------------

    def inspect_user_input(self, text: str, ctx: TurnContext | None = None) -> Decision:
        return self._decide(text, Channel.USER_INPUT, ctx or TurnContext.new())

    def inspect_tool_result(self, result: ToolResult, ctx: TurnContext | None = None) -> Decision:
        d = self._decide(result.text, Channel.TOOL_RESULT,
                         ctx or TurnContext.new(), meta_tool=result.call.name)
        if d.action is Action.BLOCK:
            # The agent never sees withheld content.
            return self._finish(Decision(
                Action.BLOCK,
                tuple(dict.fromkeys(d.labels + (Label.CONTENT_BLOCKED,))),
                d.reasons, "[sentinel: content withheld]", d.report, d.ctx))
            # note: _decide already audited; _finish only re-labels metrics hooks
        return d

    def inspect_outbound(self, text: str, tool: ToolCall | None = None,
                         ctx: TurnContext | None = None) -> Decision:
        return self._decide(text, Channel.OUTBOUND, ctx or TurnContext.new(),
                            meta_tool=tool.name if tool else None)

    # ---- core ------------------------------------------------------------

    def _decide(self, text: str, channel: Channel, ctx: TurnContext,
                meta_tool: str | None = None) -> Decision:
        report = rules.scan(text, channel)

        breach = report.elapsed_us > self.latency_budget_us
        labels: list[Label] = []
        action = Action.ALLOW

        has_block = any(fd.severity in self.block_on for fd in report.findings)

        if breach:
            labels.append(Label.LATENCY_BUDGET_BREACH)
            if channel is not Channel.USER_INPUT:
                # fail closed on untrusted lanes when we could not finish scanning
                action = Action.BLOCK
                if Label.CONTENT_BLOCKED not in labels:
                    labels.append(Label.CONTENT_BLOCKED)
        elif report.findings:
            top = report.max_severity
            if top in self.block_on:
                action = Action.BLOCK
                labels.append(Label.CONTENT_BLOCKED)
            elif top in self.redact_on and channel is not Channel.USER_INPUT:
                action = Action.REDACT
                labels.append(Label.CONTENT_REDACTED)

        labels.extend(l for l in self._semantic_labels(report) if l not in labels)

        reasons = tuple(dict.fromkeys(fd.rule_id for fd in report.findings))
        text_out = None
        if action is Action.REDACT:
            text_out = rules.redact(text, report)
        elif action is Action.BLOCK and not breach:
            text_out = "[sentinel: content withheld]" if channel is Channel.TOOL_RESULT else None

        decision = Decision(action, tuple(labels), reasons, text_out, report, ctx)
        self._audit(decision, channel, meta_tool, breach)
        self._breaker_hooks(decision, ctx)
        return decision

    def _semantic_labels(self, report: ScanReport) -> list[Label]:
        out: list[Label] = []
        ids = {fd.rule_id for fd in report.findings}
        if any(i.startswith("INJ_") for i in ids):
            out.append(Label.INJECTION_ATTEMPT)
        if any(i.startswith("SECRET_") or i.startswith("OUT_SECRET") for i in ids):
            out.append(Label.SECRET_EXPOSURE)
        if "EXFIL_MARKDOWN_IMAGE" in ids:
            out.append(Label.EXFIL_ATTEMPT)
        if any(i.startswith("OUT_") for i in ids) and not any(
                i.startswith("OUT_URL") for i in ids):
            out.append(Label.POLICY_VIOLATION)
        return out

    def _breaker_hooks(self, d: Decision, ctx: TurnContext) -> None:
        adverse = bool({Label.INJECTION_ATTEMPT, Label.EXFIL_ATTEMPT,
                        Label.LATENCY_BUDGET_BREACH} & set(d.labels))
        if adverse:
            tripped = self.breaker.record_adverse(ctx.tenant_id)
            if tripped:
                self.audit.record("BREAKER_OPEN", [Label.BREAKER_TRIPPED.value],
                                  [], ctx.tenant_id, "", {"tenant": ctx.tenant_id})

    def breaker_allows(self, tenant_id: str) -> bool:
        """Call before spending model tokens for a tenant; fail closed."""
        return not self.breaker.is_open(tenant_id)

    # ---- plumbing -----------------------------------------------------

    def _audit(self, d: Decision, channel: Channel, meta_tool: str | None,
               breach: bool) -> None:
        excerpt = d.report.findings[0].excerpt if d.report.findings else ""
        self.audit.record(
            d.action.value,
            [l.value for l in d.labels],
            list(d.reasons),
            channel.value,
            excerpt,
            {
                "tenant": d.ctx.tenant_id,
                "session": d.ctx.session_id,
                "turn": d.ctx.turn_id,
                "tool": meta_tool or "",
                "scan_us": round(d.report.elapsed_us, 1),
                "breach": breach,
            },
        )

    def _finish(self, d: Decision) -> Decision:
        return d

    def verify_chain(self) -> tuple[bool, int, str | None]:
        return self.audit.verify()

    def close(self):
        self.audit.close()
