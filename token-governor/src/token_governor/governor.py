"""Governor: the front-door API tying budgets, router, breakers, ledger."""

from __future__ import annotations

import os

from .breaker import BreakerPolicy, RunawayBreaker
from .budgets import Budgets
from .ledger import OutcomeLedger
from .models import SpendStatus, TurnContext
from .pricing import PriceTable
from .router import CascadeRouter, RoutedCall


class SpendRefused(RuntimeError):
    """Raised when a HARD cap or open breaker refuses the call."""


class Governor:
    def __init__(self, state_dir: str | os.PathLike = ".governor",
                 prices: PriceTable | None = None,
                 breaker_policy: BreakerPolicy | None = None):
        self.state = os.fspath(state_dir)
        self.prices = prices or PriceTable()
        self.budgets = Budgets()
        self.breaker = RunawayBreaker(breaker_policy)
        self.ledger = OutcomeLedger(os.path.join(self.state, "outcomes.jsonl"))
        self.router = CascadeRouter(
            self.prices,
            budget_precheck=self._precheck,
            budget_commit=self._commit,
        )

    # ---- configuration -------------------------------------------------

    def set_tenant_cap(self, tenant_id: str, cap_usd: float, soft_frac: float = 0.8):
        self.budgets.set_cap("tenant", tenant_id, cap_usd, soft_frac)

    def set_workflow_cap(self, tenant_id: str, workflow: str,
                         cap_usd: float, soft_frac: float = 0.8):
        self.budgets.set_cap("workflow", f"{tenant_id}:{workflow}", cap_usd, soft_frac)

    # ---- gating (used by CascadeRouter via callables) -------------------

    def _precheck(self, ctx: TurnContext, est_usd: float) -> SpendStatus:
        return self.budgets.precheck(ctx.tenant_id, ctx.workflow, est_usd)

    def _commit(self, ctx: TurnContext, usd: float) -> list[str]:
        return self.budgets.commit(ctx.tenant_id, ctx.workflow, usd)

    # ---- public path ------------------------------------------------------

    def gated_call(self, ctx: TurnContext, prompt_tokens: int,
                   max_output_tokens: int,
                   generate, quality_ok=None, force_tier=None) -> RoutedCall:
        ok, why = self.breaker.allow(ctx.session_id)
        if not ok:
            raise SpendRefused(f"session breaker: {why}")

        out = self.router.route(ctx, prompt_tokens, max_output_tokens,
                                generate, quality_ok, force_tier)
        if out.refused_reason and not out.hops:
            raise SpendRefused(out.refused_reason)

        for h in out.hops:
            self.ledger.record_call(ctx.session_id,
                                    {"tenant": ctx.tenant_id, "workflow": ctx.workflow},
                                    h.model, h.cost_usd)
            failed_hop = h is not out.hops[-1]      # any non-final hop was an escalation fail
            self.breaker.observe(ctx.session_id, h.cost_usd, failed=failed_hop)
        if out.refused_reason:
            raise SpendRefused(out.refused_reason)
        return out

    # ---- outcome lifecycle --------------------------------------------------

    def begin_outcome(self, ctx: TurnContext):
        self.ledger.open_outcome(ctx.session_id,
                                 {"tenant": ctx.tenant_id, "workflow": ctx.workflow})

    def end_outcome(self, ctx: TurnContext, success: bool):
        self.ledger.close_outcome(ctx.session_id,
                                  {"tenant": ctx.tenant_id, "workflow": ctx.workflow},
                                  success)
