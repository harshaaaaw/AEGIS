"""AEGIS TUI - consumer dashboard that feels like Claude Code / Codex terminal.

One screen to watch the flow, get notified, and manage anything.
No cluster, no browser, just:  aegis tui
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import cast

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Header, Log, Static, TabbedContent, TabPane


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def _demo_events() -> list[dict[str, str]]:
    n = _now()
    return [
        {"time": n, "subsystem": "Ship Gate", "kind": "CERTIFY", "msg": "support-bot v3 -> CERTIFY (replay ok, shield ok, eval 0.92)"},
        {"time": n, "subsystem": "SwapWatch", "kind": "CHECK", "msg": "run_9f3c drift false (cohen_d 0.04)"},
        {"time": n, "subsystem": "ROI Attest", "kind": "REPORT", "msg": "decision d1: net $3.00 cost $1.00 benefit $4.00"},
        {"time": n, "subsystem": "Autonomous Ops", "kind": "TIER", "msg": "tenant acme: shadow -> live (approved)"},
    ]


def _demo_verdicts() -> list[dict[str, str]]:
    return [
        {"id": "v_9f3c1a", "agent": "support-bot", "tenant": "acme", "decision": "CERTIFY", "reason": "all suites green"},
        {"id": "v_7b2e4d", "agent": "coder", "tenant": "acme", "decision": "BLOCK", "reason": "shield: prompt injection on turn 2"},
        {"id": "v_3a8f11", "agent": "analyst", "tenant": "demo", "decision": "CERTIFY", "reason": "causal estimate ok"},
    ]


def _demo_agents() -> list[dict[str, str]]:
    return [
        {"name": "claude", "cmd": "claude --print", "status": "ready", "last": "certified 2 runs"},
        {"name": "codex", "cmd": "codex exec", "status": "ready", "last": "idle"},
        {"name": "hermes", "cmd": "hermes agent", "status": "ready", "last": "connected"},
        {"name": "openclaw", "cmd": "openclaw run", "status": "ready", "last": "idle"},
        {"name": "generic", "cmd": "my-agent --flag", "status": "custom", "last": "use: aegis agent generic --cmd '...'"},
    ]


def _demo_skills() -> list[dict[str, str]]:
    return [
        {"name": "aegis-certify", "desc": "Certify a run before merge", "status": "enabled *"},
        {"name": "aegis-watch", "desc": "Live flow + notifications", "status": "enabled *"},
        {"name": "aegis-drift", "desc": "SwapWatch drift check", "status": "enabled *"},
        {"name": "aegis-posture", "desc": "One view for CISO/CFO/CTO", "status": "enabled *"},
        {"name": "aegis-gate", "desc": "Policy and injection guard", "status": "enabled"},
        {"name": "aegis-roi", "desc": "Cost vs benefit attestation", "status": "enabled"},
    ]


class FlowLog(Log):
    def on_mount(self) -> None:
        self.write_line("[bold green]AEGIS flow -- live[/]  [dim]q quit  r refresh  c certify  a agents  s skills[/]")
        for e in _demo_events():
            self.write_line(f"[dim]{e['time']}[/] [cyan]{e['subsystem']}[/] {e['kind']:8} {e['msg']}")
        self.write_line("[dim]-- waiting for next event (aegis agent ... will appear here) --[/]")


class AegisTUI(App):
    """Premium TUI: dashboard, flow, runs, agents, skills. No browser needed."""

    CSS = """
    Header { background: #0a0a0a; color: #00ff88; }
    #nav { width: 22; background: #111111; }
    #main { background: #0a0a0a; }
    #detail { width: 32; background: #111111; }
    DataTable { height: 1fr; }
    Log { height: 1fr; background: #0a0a0a; }
    Button { margin: 1; }
    """

    TITLE = "AEGIS -- control plane"
    SUB_TITLE = "trust, govern, prove"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="nav"):
                yield Static("[bold]AEGIS[/]\n[dim]one room, one spine[/]", id="brand")
                yield Static(
                    "\n[bold]Navigate[/]\n1 Dashboard\n2 Flow\n3 Runs\n4 Agents\n5 Skills\n\n"
                    "[dim]Keys:[/]\n q quit\n r refresh\n c certify demo\n a connect agent\n s install skill",
                    id="help",
                )
                yield Button("Certify demo run", id="btn_certify", variant="success")
                yield Button("Connect agent", id="btn_agent", variant="primary")
            with TabbedContent(id="main", initial="dash"):
                with TabPane("Dashboard", id="dash"):
                    yield Static("[bold]Dashboard[/]  [dim]consumer view -- what matters now[/]\n", id="dash_title")
                    verds: DataTable = DataTable(id="tbl_verdicts")
                    yield verds
                    yield Static(
                        "\n[dim]Tip: press 2 for Flow, 4 for Agents, 5 for Skills. c runs a demo certify.[/]"
                    )
                with TabPane("Flow", id="flow"):
                    yield FlowLog(id="flow_log", highlight=True)
                with TabPane("Runs", id="runs"):
                    yield Static("[bold]Runs[/]  [dim]recent certify attempts[/]\n")
                    tbl: DataTable = DataTable(id="tbl_runs")
                    yield tbl
                with TabPane("Agents", id="agents"):
                    yield Static(
                        "[bold]Agents[/]  [dim]connect any agent to the same Spine[/]\n"
                        "[dim]Each has its own command. Generic works with any CLI.[/]\n"
                    )
                    atbl: DataTable = DataTable(id="tbl_agents")
                    yield atbl
                    yield Static(
                        "\n[dim]Examples:[/]\n"
                        "  aegis agent claude \"summarize this repo\"\n"
                        "  aegis agent codex \"fix tests\"\n"
                        "  aegis agent hermes \"run plan\"\n"
                        "  aegis agent openclaw \"ship feature\"\n"
                        "  aegis agent generic --cmd \"my-agent --flag\" \"task\"",
                        id="agent_help",
                    )
                with TabPane("Skills", id="skills"):
                    yield Static(
                        "[bold]Skills[/]  [dim]installed and grounded to the flow[/]\n"
                        "[dim]Required skills are starred. They enforce the objective before any ship.[/]\n"
                    )
                    stbl: DataTable = DataTable(id="tbl_skills")
                    yield stbl
                    yield Static(
                        "\n[dim]Install more:[/]  aegis skill install <name>"
                        "   [dim]e.g. aegis skill install aegis-roi[/]\n"
                        "[dim]List:[/]  aegis skill list",
                        id="skill_help",
                    )
            with Vertical(id="detail"):
                yield Static("[bold]Notifications[/] [dim]live[/]\n", id="notif_title")
                yield Log(id="notif_log", highlight=True)
                yield Static("\n[bold]Posture[/] [dim]one view[/]\n", id="posture_title")
                yield Static(
                    "tenant: acme\ntrust tier: live\nopen drifts: 0\nsigned verdicts: 3\n[dim]aegis posture shows full json[/]",
                    id="posture_body",
                )

    def on_mount(self) -> None:
        vt = self.query_one("#tbl_verdicts", DataTable)
        vt.add_columns("verdict", "agent", "tenant", "decision", "reason")
        for v in _demo_verdicts():
            color = "green" if v["decision"] == "CERTIFY" else "red"
            vt.add_row(v["id"], v["agent"], v["tenant"], f"[{color}]{v['decision']}[/]", v["reason"])
        rt = self.query_one("#tbl_runs", DataTable)
        rt.add_columns("run", "agent", "tenant", "status")
        for v in _demo_verdicts():
            rt.add_row(v["id"].replace("v_", "run_"), v["agent"], v["tenant"], v["decision"])
        at = self.query_one("#tbl_agents", DataTable)
        at.add_columns("agent", "command", "status", "last")
        for a in _demo_agents():
            at.add_row(a["name"], a["cmd"], a["status"], a["last"])
        st = self.query_one("#tbl_skills", DataTable)
        st.add_columns("skill", "what it does", "status")
        for s in _demo_skills():
            st.add_row(s["name"], s["desc"], s["status"])
        nl = self.query_one("#notif_log", Log)
        nl.write_line("[green]Certify ok[/] v_9f3c1a acme/support-bot")
        nl.write_line("[yellow]Drift check[/] run_9f3c false d=0.04")
        nl.write_line("[dim]No policy blocks in last hour.[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_certify":
            self._demo_certify()
        elif event.button.id == "btn_agent":
            self._show_agents()

    def _demo_certify(self) -> None:
        log = self.query_one("#flow_log", FlowLog)
        nl = cast(Log, self.query_one("#notif_log"))
        ts = _now()
        vid = f"v_demo_{int(time.time())%10000}"
        log.write_line(f"[dim]{ts}[/] [cyan]Ship Gate[/] CERTIFY  demo -> {vid} [green]CERTIFY[/]")
        nl.write_line(f"[green]{ts} CERTIFY[/] demo run -> CERTIFY")

    def _show_agents(self) -> None:
        tc = self.query_one("#main", TabbedContent)
        tc.active = "agents"

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key in ("1", "2", "3", "4", "5"):
            mapping = {"1": "dash", "2": "flow", "3": "runs", "4": "agents", "5": "skills"}
            cast(TabbedContent, self.query_one("#main")).active = mapping[event.key]
        elif event.key == "c":
            self._demo_certify()
        elif event.key == "a":
            cast(TabbedContent, self.query_one("#main")).active = "agents"
        elif event.key == "s":
            cast(TabbedContent, self.query_one("#main")).active = "skills"
        elif event.key == "r":
            cast(FlowLog, self.query_one("#flow_log")).write_line(f"[dim]{_now()} refresh[/] no new events")


def run_tui() -> None:
    app = AegisTUI()
    app.run()
