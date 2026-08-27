# token-governor

**Budgets, kill switches, and cost-per-successful-outcome accounting for LLM agent fleets.**

Agents now spend money every turn. token-governor is the finance layer: per-tenant and per-workflow spend caps, a runaway breaker that cuts a session before it burns the budget, cascade routing to a cheaper model when the premium one is over cap, and a ledger that reports cost per outcome that actually succeeded. No more "we don't know what that agent cost us."

## Why this is the room the bill shows but the dashboard hides

Observability tools show you spend after the fact. token-governor enforces before the fact: a `Governor` refuses a call that would blow the tenant or workflow cap, a `RunawayBreaker` trips on sustained over-budget turns, and a `CascadeRouter` drops to a cheaper model instead of failing. The ledger rolls up spend into outcomes, so "cost per resolved ticket" is a real number, not a guess.

## What it actually does

- **Governor / Budgets**: per-tenant and per-workflow daily USD caps; `SpendRefused` on breach.
- **BreakerPolicy / RunawayBreaker**: trip when spend runs away, not after the invoice.
- **CascadeRouter / Hop / RoutedCall**: route to a fallback model tier when the primary is over cap.
- **PriceTable**: model pricing in one place, used for every charge.
- **OutcomeLedger / OutcomeRollup**: cost attributed to successful outcomes, not raw tokens.

## Quickstart

```bash
pip install -e "./token-governor"

from token_governor import Governor, PriceTable

g = Governor(state_dir="./st")
g.set_tenant_cap("acme", 1.00)
g.set_workflow_cap("acme", "support", 0.50)

def model_call(model, tier):
    return 120, 80   # in_tok, out_tok

record = g.charge("acme", "support", "gpt-x", model_call)
print(record.status)   # SpendStatus.CHARGED or SpendStatus.REFUSED
```

## Quality (measured)

| Signal | Value |
|---|---|
| Tests | 11 green (caps, breaker, cascade, ledger rollup) |
| Ruff | clean |
| Mypy | clean |
| Bandit | clean (no asserts in validation paths, no weak crypto) |

Run: `pytest token-governor/tests/ -q`

## Honest limitations

- Pricing is a `PriceTable` you populate; the package does not scrape live provider prices.
- Cost-per-outcome requires you to report outcomes back to the `OutcomeLedger`. The rollup is only as honest as the outcomes you record.

## License

MIT.
