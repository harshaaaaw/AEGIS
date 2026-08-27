"""Chaos-flavored tests: budgets must hold under hostile patterns."""

import pytest

from token_governor import (
    BreakerPolicy, Governor, PriceTable, SpendRefused, SpendStatus,
    TurnContext,
)


def make_gov(tmp_path, tenant_cap=1.00, wf_cap=0.50):
    g = Governor(state_dir=tmp_path / "st")
    g.set_tenant_cap("acme", tenant_cap)
    g.set_workflow_cap("acme", "support", wf_cap)
    return g


def gen_ok(in_toks, out_toks):
    """generate() stub that 'calls' the model successfully."""
    def _g(model, tier):
        return in_toks, out_toks
    return _g


# ---- pricing ------------------------------------------------------------

def test_pricing_family_fallback():
    p = PriceTable()
    assert p.get("cheap") == (0.25, 1.25)
    with pytest.raises(KeyError):
        p.get("unknown-model-xyz")


# ---- cascade economics ----------------------------------------------------

def test_cheap_first_passes_at_lowest_cost(tmp_path):
    g = make_gov(tmp_path)
    ctx = TurnContext.new(tenant_id="acme", workflow="support")
    out = g.gated_call(ctx, prompt_tokens=1000, max_output_tokens=500,
                       generate=gen_ok(1000, 300), quality_ok=lambda: True)
    assert out.final_model == "cheap"
    assert len(out.hops) == 1
    # 1000 * 0.25/1M + 300 * 1.25/1M = 0.000625
    assert abs(out.total_cost_usd - 0.000625) < 1e-9


def test_failed_quality_escalates_and_meters_every_hop(tmp_path):
    g = make_gov(tmp_path)
    ctx = TurnContext.new(tenant_id="acme", workflow="support")
    checks = iter([False, False, True])     # cheap fails, mid fails, frontier passes
    out = g.gated_call(ctx, 1000, 500, gen_ok(1000, 400),
                       quality_ok=lambda: next(checks))
    assert out.final_model == "frontier"
    assert out.escalations == 2
    assert len(out.hops) == 3               # all three hops metered
    expected = (1000*0.25 + 400*1.25 + 1000*3.0 + 400*15.0 + 1000*15.0 + 400*75.0) / 1e6
    assert abs(out.total_cost_usd - expected) < 1e-9


def test_force_frontier_skips_cheaper_tiers(tmp_path):
    g = make_gov(tmp_path)
    ctx = TurnContext.new(tenant_id="acme", workflow="support")
    seen = []
    def gen(model, tier):
        seen.append(tier); return 10, 5
    out = g.gated_call(ctx, 100, 50, gen, force_tier=2)
    assert seen == ["frontier"] and out.escalations == 0


# ---- budgets ----------------------------------------------------------------

def test_hard_workflow_cap_refuses_before_spend(tmp_path):
    g = make_gov(tmp_path, tenant_cap=10.0, wf_cap=0.001)
    ctx = TurnContext.new(tenant_id="acme", workflow="support")
    # frontier estimate alone blows the 0.001 cap -> refuse at door
    with pytest.raises(SpendRefused):
        g.gated_call(ctx, 100_000, 50_000,
                     gen_ok(100, 10), force_tier=2)


def test_soft_threshold_fires_alert_once(tmp_path):
    g = Governor(state_dir=tmp_path / "s")
    g.set_tenant_cap("acme", cap_usd=0.001, soft_frac=0.5)
    ctx = TurnContext.new(tenant_id="acme", workflow="w")
    alerts = []
    orig_commit = g.budgets.commit
    def spy(t, w, usd):
        evs = orig_commit(t, w, usd)
        alerts.extend(evs); return evs
    g.budgets.commit = spy
    for _ in range(4):
        try:
            g.gated_call(ctx, 1000, 200, gen_ok(1000, 200))
        except SpendRefused:
            pass                            # expected once HARD cap bites
    soft_events = [a for a in alerts if a.startswith("SOFT")]
    hard_events = [a for a in alerts if a.startswith("HARD")]
    assert len(soft_events) == 1            # fired exactly once
    assert hard_events                      # cap eventually reached


def test_unscoped_tenant_spends_freely(tmp_path):
    g = Governor(state_dir=tmp_path / "u")
    ctx = TurnContext.new(tenant_id="nobody", workflow="x")
    out = g.gated_call(ctx, 1000, 100, gen_ok(1000, 100))
    assert out.total_cost_usd > 0           # no caps declared -> allowed


# ---- runaway breakers ----------------------------------------------------------

def test_breaker_opens_on_retry_storm(tmp_path):
    g = Governor(
        state_dir=tmp_path / "b",
        breaker_policy=BreakerPolicy(max_spend_usd=0.01, window_seconds=60,
                                     cooldown_seconds=3600),
    )
    ctx = TurnContext.new(tenant_id="acme", workflow="storm")
    with pytest.raises(SpendRefused):
        for _ in range(200):                 # storm of frontier-ish calls
            try:
                g.gated_call(ctx, 30_000, 20_000, gen_ok(30_000, 20_000))
            except SpendRefused:
                raise
    ok, why = g.breaker.allow(ctx.session_id)
    assert not ok and "breaker open" in why


def test_breaker_trips_on_consecutive_failures(tmp_path):
    g = Governor(state_dir=tmp_path / "f",
                 breaker_policy=BreakerPolicy(max_consecutive_failures=3,
                                              max_spend_usd=999, max_calls=999))
    ctx = TurnContext.new(tenant_id="acme", workflow="flaky")
    checks = iter([False, False, True])
    g.gated_call(ctx, 10, 5, gen_ok(10, 5), quality_ok=lambda: next(checks))
    for _ in range(2):
        g.breaker.observe(ctx.session_id, 0.0, failed=True)
    g.breaker.observe(ctx.session_id, 0.0, failed=True)   # third failure trips
    assert g.breaker.is_open(ctx.session_id)


# ---- outcome ledger ------------------------------------------------------------

def test_cost_per_success_and_retry_waste(tmp_path):
    g = make_gov(tmp_path, tenant_cap=100.0)
    good = TurnContext.new(tenant_id="acme", workflow="sup")
    bad = TurnContext.new(tenant_id="acme", workflow="sup")

    g.begin_outcome(good)
    g.gated_call(good, 1000, 500, gen_ok(1000, 500))       # cheap pass: 0.000875
    g.end_outcome(good, success=True)

    g.begin_outcome(bad)
    checks = iter([False, True])
    g.gated_call(bad, 1000, 500, gen_ok(1000, 500),
                 quality_ok=lambda: next(checks))           # cheap fail + mid pass
    g.end_outcome(bad, success=False)

    r = g.ledger.rollup(tenant="acme")
    assert r.outcomes_total == 2 and r.outcomes_success == 1
    assert r.calls_total == 3
    assert r.retry_waste_usd > 0                            # failed session's cost counted as waste
    assert r.cost_per_success_usd == (r.cost_total_usd / 1)


def test_ledger_conservation_calls_match_hops(tmp_path):
    g = make_gov(tmp_path, tenant_cap=100.0)
    for i in range(3):
        ctx = TurnContext.new(tenant_id="acme", workflow="sup")
        g.gated_call(ctx, 100, 50, gen_ok(100, 50))
    r = g.ledger.rollup()
    assert r.calls_total == 3
