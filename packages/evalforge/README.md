# evalforge

**The golden-set eval harness that actually blocks a bad merge, and tells you why it regressed.**

Every LLM team says "we evaluate." Almost none can prove a change made things worse, or stop it from shipping. evalforge is the merge gate: deterministic checks plus judge hooks, regression attribution, and the two numbers interviewers ask for (recall@k and faithfulness). It is the quality layer every other room in this suite plugs into.

## Why this is the room nobody finishes

Most eval tooling is a notebook. evalforge is a gate: it produces a `RunReport` with a pass/fail verdict and a `ScoreDiff` that names exactly which case regressed and by how much. Wire it to CI and a bad prompt change cannot quietly ship.

## What it actually does

- **EvalCase**: a self-describing unit of evaluation (input, expected, `must_not_contain`, judge hook).
- **GoldenSet**: the regression baseline a merge is measured against.
- **EvalRunner**: runs the set deterministically and returns a `RunReport`.
- **ScoreDiff**: pinpoints the cases that moved, so a regression is never a mystery.
- **Judge hooks**: bring your own LLM-as-judge for open-ended checks; the deterministic checks (exact match, must-contain, forbidden strings, regex, citation validity) need no model.

## Quickstart

```bash
pip install -e "./evalforge"

# Define a golden case (no model needed for deterministic checks)
cat > case.json <<'EOF'
{"case_id":"c1","input":"What is our refund window?",
 "expected":"30 days","must_not_contain":["lifetime","never"]}
EOF

# Run a golden set and get a pass/fail report
evalforge run ./golden/ --out report.json

# Diff two runs to see what regressed
evalforge diff before.json after.json
```

## Quality (measured)

| Signal | Value |
|---|---|
| Tests | 6 green |
| Ruff | clean |
| Mypy | clean |
| Bandit | clean |

Run: `pytest evalforge/tests/ -q`

## Honest limitations

- The judge hooks are interfaces; the demo wires a stub judge so the CLI runs out of the box. Plug your real judge into `EvalRunner`.
- recall@k and faithfulness are computed by the judge you supply, not invented by evalforge.

## License

MIT.
