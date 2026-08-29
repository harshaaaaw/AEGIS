"""Detection rules with a two-tier prefilter for latency.

Design note (measured, see benchmarks/): merging rules into one big
alternation is SLOWER than separate passes under Python's re engine
(15ms vs 8.6ms on 58KB) because every position pays for every branch.
The winning structure:

  Tier 1 - distinctive-shape rules (secrets, md-image, fake markers,
           outbound URLs): always scanned; their anchors are rare so
           they fail fast on ordinary text.
  Tier 2 - natural-language injection phrases: scanned ONLY when at
           least one trigger word exists in the text. A single C-speed
           substring sweep gates five expensive regexes, which lets
           ordinary business documents skip the whole tier.

Adversarial content that does trip tier 2 pays full price; if that
exceeds the enforced budget the shield fails closed (BLOCK), which is
the safe direction to be wrong in.
"""

from __future__ import annotations

import re

from .models import Channel, Finding, ScanReport, Severity, now_us


def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# ---- tier 1: distinctive shapes ----------------------------------------

_T1_RULES = [
    ("SECRET_OPENAI", _c(r"\bsk-[A-Za-z0-9_-]{16,}\b"), Severity.CRITICAL,
     "OpenAI-style API key shape."),
    ("SECRET_AWS", _c(r"\bAKIA[0-9A-Z]{16}\b"), Severity.CRITICAL,
     "AWS access key id shape."),
    ("SECRET_SLACK", _c(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), Severity.CRITICAL,
     "Slack token shape."),
    ("SECRET_PK", _c(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), Severity.CRITICAL,
     "Embedded private key."),
    ("EXFIL_MARKDOWN_IMAGE", _c(r"!\[[^\]]*\]\((?:https?:)?//[^)]{4,}\)"),
     Severity.HIGH,
     "Markdown image: remote fetch rendered into model/human context."),
]

_FAKE_SYS = ("INJ_FAKE_SYS",
             _c(r"(?:^|\n)\s*(?:system\s*:|assistant\s*:|\[system\]|"
                r"<\|(?:system|im_start)\|>)"),
             Severity.CRITICAL, "Fake chat-role marker in untrusted content.")

_OUT_URL = ("OUT_URL_LOGGED",
            _c(r"\bhttps?://[^\s\"'<>]{12,}"), Severity.LOW,
            "Outbound URL recorded (logged, allowed by default).")

_HYGIENE_INPUT = ("SECRET_SHAPED_INPUT",
                  _c(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|"
                     r"xox[baprs]-[A-Za-z0-9-]{10,})\b"),
                  Severity.MEDIUM,
                  "Credential-like string in user input; labeled, allowed.")

# ---- tier 2: phrase-level injection rules -------------------------------

_T2_RULES = [
    ("INJ_OVERRIDE", _c(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?"
        r"(?:previous|prior|earlier|above|preceding)\s+"
        r"(?:instructions?|prompts?|rules?|directions?)"),
     Severity.CRITICAL, "Instruction-override attempt."),
    ("INJ_ROLE", _c(
        r"\byou\s+are\s+(?:now\s+)?(?:in\s+)?(?:a\s+)?"
        r"(?:developer|dan|admin(?:istrator)?|root|unrestricted)\s+mode"),
     Severity.CRITICAL, "Role/mode hijack attempt."),
    ("INJ_REVEAL", _c(
        r"\b(?:reveal|print|repeat|output|disclose|show\s+me|disregard)\b"
        r"[^.\n]{0,60}\b(?:system\s+prompt|initial\s+(?:instructions?|prompts?)|"
        r"(?:previous|prior)\s+(?:instructions?|prompts?)|developer\s+messages?)\b"),
     Severity.CRITICAL, "System-prompt extraction attempt."),
    ("INJ_TOOL_HIJACK", _c(
        r"\b(?:use|call|invoke)\s+the\s+\w+\s*(?:tool|function)\b[^.\n]{0,80}"
        r"\b(?:send|post|email|transfer|delete|drop|forward)\b"),
     Severity.CRITICAL, "Tool weaponization instruction."),
]

# if NONE of these appear (lowercased), tier-2 rules cannot match
_T2_TRIGGERS = (
    "ignore", "disregard", "forget", "you are", "mode", "reveal", "print",
    "repeat", "output", "disclose", "show me", "use the", "call the",
    "invoke the", "system:", "assistant:", "[system]",
)

_MAX_HITS_PER_RULE = 5


def _run(text: str, rule_set) -> list[Finding]:
    out: list[Finding] = []
    counts: dict[str, int] = {}
    for rid, pat, sev, det in rule_set:
        n = 0
        for m in pat.finditer(text):
            s, e = m.span()
            out.append(Finding(
                rid, sev, (s, e),
                text[max(0, s - 40):min(len(text), e + 40)].replace("\n", "\\n"),
                det))
            n += 1
            if n >= _MAX_HITS_PER_RULE:
                break
        counts[rid] = n
    return out


def scan(text: str, channel: Channel) -> ScanReport:
    t0 = now_us()
    report = ScanReport(channel=channel, text_len=len(text))
    f: list[Finding] = []
    low = text.lower()

    if channel is Channel.USER_INPUT:
        # trusted lane: hygiene labeling only, never blocked here
        f.extend(_run(text, [_HYGIENE_INPUT]))
        report.findings = f
        report.elapsed_us = now_us() - t0
        return report

    # tier 1 always
    t1 = list(_T1_RULES)
    t1.append(_FAKE_SYS)
    if channel is Channel.OUTBOUND:
        t1.append(_OUT_URL)
    f.extend(_run(text, t1))

    # tier 2 gated on trigger sweep
    if any(t in low for t in _T2_TRIGGERS):
        f.extend(_run(text, _T2_RULES))

    report.findings = f
    report.elapsed_us = now_us() - t0
    return report


def redact(text: str, report: ScanReport) -> str:
    """Cut MEDIUM+ severity spans out of text, keep everything else intact."""
    spans = sorted((fd.span for fd in report.findings
                    if fd.severity >= Severity.MEDIUM), reverse=True)
    for s, e in spans:
        text = text[:s] + "[REDACTED]" + text[e:]
    return text
