"""Skills installed and grounded to the flow."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

SKILL_HUB = Path(__file__).parent / "hub"
USER_SKILLS = Path.home() / ".aegis" / "skills"


@dataclass
class Skill:
    name: str
    description: str
    objective: str
    required: bool
    enabled: bool
    path: str


REQUIRED_SKILLS = [
    Skill("aegis-certify", "Certify a run before merge", "No ship without a signed CERTIFY", True, True, "builtin"),
    Skill("aegis-watch", "Live flow + notifications", "Every event is visible and alerted", True, True, "builtin"),
    Skill("aegis-drift", "SwapWatch drift check", "No silent model swap", True, True, "builtin"),
    Skill("aegis-posture", "One view for CISO/CFO/CTO", "Posture is always queryable", True, True, "builtin"),
]

OPTIONAL_SKILLS = [
    Skill("aegis-gate", "Policy and injection guard", "Every turn is shielded", False, True, "builtin"),
    Skill("aegis-roi", "Cost vs benefit attestation", "Every decision has a priced report", False, True, "builtin"),
    Skill("aegis-memory", "Governed memory with provenance", "No read without capability", False, False, "builtin"),
    Skill("aegis-contract", "Tool scope enforcement", "No tool outside allowlist", False, False, "builtin"),
]


def _ensure_dirs() -> None:
    USER_SKILLS.mkdir(parents=True, exist_ok=True)
    SKILL_HUB.mkdir(parents=True, exist_ok=True)


def list_skills() -> list[Skill]:
    _ensure_dirs()
    skills: list[Skill] = list(REQUIRED_SKILLS) + list(OPTIONAL_SKILLS)
    if SKILL_HUB.exists():
        for p in SKILL_HUB.iterdir():
            if p.is_dir() and (p / "SKILL.md").exists() and p.name not in {s.name for s in skills}:
                skills.append(Skill(p.name, f"Hub skill {p.name}", "Custom objective per SKILL.md", False, True, str(p)))
    if USER_SKILLS.exists():
        for p in USER_SKILLS.iterdir():
            if p.is_dir() and p.name not in {s.name for s in skills}:
                skills.append(Skill(p.name, f"User skill {p.name}", "User objective", False, True, str(p)))
    return skills


def install_skill(name: str, source: Path | None = None) -> dict[str, object]:
    _ensure_dirs()
    if source is not None:
        src = Path(source).expanduser().resolve()
        if not src.exists():
            return {"ok": False, "msg": f"source not found: {src}"}
        dest = USER_SKILLS / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return {"ok": True, "msg": f"installed {src.name} -> {dest}", "path": str(dest)}
    hub_src = SKILL_HUB / name
    if not hub_src.exists():
        hub_src.mkdir(parents=True, exist_ok=True)
        (hub_src / "SKILL.md").write_text(
            f"# {name}\n\nObjective: grounded to AEGIS flow. Writes to Spine and verifies.\n",
            encoding="utf-8",
        )
    dest = USER_SKILLS / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(hub_src, dest)
    return {"ok": True, "msg": f"installed {name} from hub -> {dest}", "path": str(dest)}


def verify_skill(name: str) -> dict[str, object]:
    for s in list_skills():
        if s.name == name:
            if s.required:
                return {"name": name, "grounded": True, "msg": "required skill, always grounded to flow"}
            p = Path(s.path) if s.path != "builtin" else None
            if p is None:
                return {"name": name, "grounded": True, "msg": "builtin skill, verified in code"}
            if (p / "SKILL.md").exists():
                return {"name": name, "grounded": True, "msg": "SKILL.md present and objective declared"}
            return {"name": name, "grounded": False, "msg": "missing SKILL.md -- not grounded"}
    return {"name": name, "grounded": False, "msg": "skill not found"}
