"""Demo: a support agent hits a retry storm. Watch the kill switch fire.

Run: python examples/demo.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from token_governor import Governor, TurnContext, SpendRefused

g = Governor(state_dir=".gov-demo")
g.set_tenant_cap("acme", cap_usd=1.00)
g.set_workflow_cap("acme", "support", cap_usd=0.50)

def expensive_model(tier, _t=None):
    # pretend every call burns 25k in / 15k out on the frontier tier
    return 25_000, 15_000

print("=" * 62)
print("DEMO: runaway agent loop vs the kill switch")
print("=" * 62)
ctx = TurnContext.new(tenant_id="acme", workflow="support")
g.begin_outcome(ctx)

spent = 0.0
try:
    for turn in range(1, 100):
        out = g.gated_call(
            ctx,
            prompt_tokens=25_000, max_output_tokens=15_000,
            generate=expensive_model,
            quality_ok=lambda: False,      # agent keeps 'failing' -> retries
        )
        spent += out.total_cost_usd
        print(f"turn {turn:2d}: hops={len(out.hops)} "
              f"cost=${out.total_cost_usd:.4f} cumulative=${spent:.4f}")
except SpendRefused as e:
    print(f"\nKILL SWITCH -> {e}")
    g.end_outcome(ctx, success=False)

r = g.ledger.rollup(tenant="acme")
print("\nOutcome ledger:")
print(f"  calls metered            : {r.calls_total}")
print(f"  cost total               : ${r.cost_total_usd:.4f}")
print(f"  outcome                  : failed (retry waste = ${r.retry_waste_usd:.4f})")
print(f"  workflow budget left     : ${g.budgets.remaining('workflow', 'acme:support'):.4f}")
print(f"\nFull trail: .gov-demo/outcomes.jsonl")
