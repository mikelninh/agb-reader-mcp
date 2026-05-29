"""
agb-reader-mcp — German Terms-of-Service (AGB) clause checker.

Wraps the BGB §§ 305c / 307 / 308 / 309 control catalog as MCP tools. Built
on civic-ai-mcp-toolkit. Every flagged clause comes back with the exact §
citation, the rule text, the severity (unwirksam vs. wahrscheinlich
unwirksam), and a plain-German explanation.

What it answers for a citizen via Claude / Cursor / browser-extension:
  - "Lies diese AGB — was ist problematisch?"
  - "Ist diese Klausel zulässig?"
  - "Schreib mir den Widerspruch."

What this MCP is NOT:
  - Rechtsberatung im Einzelfall (für konkrete Verträge → Anwalt)
  - vollumfänglicher BGB-Klausel-Scanner (Pattern-Matching erkennt typische
    Fälle, aber nicht jeden raffinierten Versuch — siehe README "Honest limits")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from civic_ai_mcp import (
    configure_logging,
    create_mcp_server,
    error_envelope,
    load_fixture,
    run_main,
    traced,
)


HERE = Path(__file__).resolve().parent

mcp = create_mcp_server("agb-reader", default_port=8012)


# ── Helpers ──────────────────────────────────────────────────────────


def _v309() -> list[dict[str, Any]]:
    return load_fixture(HERE, "klauselverbote_309.json")["verbote"]


def _v308() -> list[dict[str, Any]]:
    return load_fixture(HERE, "klauselverbote_308.json")["verbote"]


def _red_flags() -> list[dict[str, Any]]:
    return load_fixture(HERE, "general_red_flags.json")["red_flags"]


def _matches_any_pattern(text: str, patterns: list[str]) -> str | None:
    """Return the first matching pattern or None."""
    text_lower = text.lower()
    for p in patterns:
        if re.search(p.lower(), text_lower):
            return p
    return None


def _matches_negative_indicator(text: str, neg_patterns: list[str] | None) -> bool:
    """True if any negative indicator (i.e. exclusion) is present."""
    if not neg_patterns:
        return False
    text_lower = text.lower()
    return any(re.search(p.lower(), text_lower) for p in neg_patterns)


# ── Tool 1: check_clause_against_309 ─────────────────────────────────


@mcp.tool()
@traced("check_clause_against_309")
def check_clause_against_309(clause_text: str) -> dict[str, Any]:
    """
    Check a single clause against § 309 BGB — Klauselverbote ohne Wertungsmöglichkeit.

    These are the 13 absolutely-forbidden clause types. A match means the clause
    is unwirksam, no balancing, no exceptions.

    Args:
      clause_text: the AGB clause text to check (in German).

    Returns:
      {
        "violations": [
          {"nr", "title", "rule", "matched_pattern", "severity", "paragraph"},
          ...
        ],
        "violation_count": <int>,
        "verdict": "unwirksam" | "wahrscheinlich_zulässig"
      }
    """
    if not clause_text or not clause_text.strip():
        return error_envelope("invalid_input", "clause_text must be non-empty")

    violations: list[dict[str, Any]] = []
    for v in _v309():
        matched = _matches_any_pattern(clause_text, v["patterns"])
        if matched and not _matches_negative_indicator(clause_text, v.get("negative_indicator")):
            violations.append(
                {
                    "nr": v["nr"],
                    "title": v["title"],
                    "rule": v["rule"],
                    "matched_pattern": matched,
                    "severity": v["severity"],
                    "paragraph": f"§ 309 Nr. {v['nr']} BGB",
                }
            )

    return {
        "violations": violations,
        "violation_count": len(violations),
        "verdict": "unwirksam" if violations else "wahrscheinlich_zulässig",
    }


# ── Tool 2: check_clause_against_308 ─────────────────────────────────


@mcp.tool()
@traced("check_clause_against_308")
def check_clause_against_308(clause_text: str) -> dict[str, Any]:
    """
    Check a clause against § 308 BGB — Klauselverbote mit Wertungsmöglichkeit.

    These 8 clause types can be unwirksam *depending on the specifics*: a
    delivery-deadline AGB clause is fine at 14 days, suspect at 60. Verdict:
    "wahrscheinlich unwirksam — kontextabhängig".

    Args:
      clause_text: the AGB clause to check (German).

    Returns:
      {
        "suspicions": [...same shape as § 309 violations],
        "suspicion_count": <int>,
        "verdict": "wahrscheinlich_unwirksam" | "wahrscheinlich_zulässig"
      }
    """
    if not clause_text or not clause_text.strip():
        return error_envelope("invalid_input", "clause_text must be non-empty")

    suspicions: list[dict[str, Any]] = []
    for v in _v308():
        matched = _matches_any_pattern(clause_text, v["patterns"])
        if matched:
            suspicions.append(
                {
                    "nr": v["nr"],
                    "title": v["title"],
                    "rule": v["rule"],
                    "matched_pattern": matched,
                    "severity": v["severity"],
                    "paragraph": f"§ 308 Nr. {v['nr']} BGB",
                }
            )

    return {
        "suspicions": suspicions,
        "suspicion_count": len(suspicions),
        "verdict": "wahrscheinlich_unwirksam" if suspicions else "wahrscheinlich_zulässig",
    }


# ── Tool 3: check_general_red_flags ──────────────────────────────────


@mcp.tool()
@traced("check_general_red_flags")
def check_general_red_flags(clause_text: str) -> dict[str, Any]:
    """
    Check a clause against the Verbraucherzentrale-style catalog of typical
    problematic AGB clauses — § 305c (überraschende Klauseln), § 307 (unangemessene
    Benachteiligung), § 306 (salvatorisch).

    These flags catch the *patterns* that show up across many AGB sets:
    Gerichtsstandsklauseln, Rechtswahl, intransparente Formulierungen, einseitige
    AGB-Änderungsvorbehalte, vorab-Werbeeinwilligung.

    Args:
      clause_text: the AGB clause to check.

    Returns:
      {
        "red_flags": [
          {"category", "matched_pattern", "paragraph", "severity", "explanation"},
          ...
        ],
        "red_flag_count": <int>
      }
    """
    if not clause_text or not clause_text.strip():
        return error_envelope("invalid_input", "clause_text must be non-empty")

    flags: list[dict[str, Any]] = []
    for f in _red_flags():
        matched = _matches_any_pattern(clause_text, f["patterns"])
        if matched and not _matches_negative_indicator(
            clause_text, [f.get("exclusion_pattern")] if f.get("exclusion_pattern") else None
        ):
            flags.append(
                {
                    "category": f["category"],
                    "matched_pattern": matched,
                    "paragraph": f["paragraph"],
                    "severity": f["severity"],
                    "explanation": f["explanation"],
                }
            )

    return {"red_flags": flags, "red_flag_count": len(flags)}


# ── Tool 4: analyze_agb ──────────────────────────────────────────────


_CLAUSE_SPLIT_RE = re.compile(
    r"(?:^|\n)\s*"
    r"(?:§|§|Nr\.|Ziff\.|Punkt|\d+\.\d+|\d+\)|[IVX]+\.)"
    r".{0,4000}?(?=(?:\n\s*(?:§|§|Nr\.|Ziff\.|Punkt|\d+\.\d+|\d+\)|[IVX]+\.))|\Z)",
    re.DOTALL,
)


def _split_into_clauses(text: str) -> list[str]:
    """Best-effort split of an AGB blob into discrete clauses. Falls back to paragraph splits."""
    matches = _CLAUSE_SPLIT_RE.findall(text)
    if matches and len(matches) > 1:
        return [m.strip() for m in matches if m.strip()]
    # Fallback: split on double-newlines
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


@mcp.tool()
@traced("analyze_agb")
def analyze_agb(agb_text: str, max_clauses: int = 100) -> dict[str, Any]:
    """
    Full-AGB analyzer — splits the input into discrete clauses, runs all three
    checkers (§ 309, § 308, general red flags) on each one, and returns a
    consolidated report ranked by severity.

    This is the tool the Chrome-extension calls. User pastes / highlights the
    AGB, gets a single structured response.

    Args:
      agb_text:    full text of the AGB block.
      max_clauses: safety cap on the number of clauses processed (default 100).

    Returns:
      {
        "clause_count":           <int>,
        "problematic_count":      <int>,
        "summary": {
          "unwirksam_count":          <int — § 309 hits>,
          "wahrscheinlich_unwirksam": <int — § 308 hits>,
          "red_flag_count":           <int — § 305c/307 hits>
        },
        "problematic_clauses": [
          {
            "clause_index":    <int>,
            "clause_excerpt":  "<first 200 chars>",
            "verdict":         "unwirksam" | "wahrscheinlich_unwirksam" | "kontextabhängig",
            "violations":      [...§ 309 hits],
            "suspicions":      [...§ 308 hits],
            "red_flags":       [...]
          },
          ...
        ]
      }
    """
    if not agb_text or not agb_text.strip():
        return error_envelope("invalid_input", "agb_text must be non-empty")

    clauses = _split_into_clauses(agb_text)[:max_clauses]
    problematic: list[dict[str, Any]] = []
    n_unwirksam = 0
    n_wahrscheinlich = 0
    n_red_flag = 0

    for i, clause in enumerate(clauses):
        v309 = check_clause_against_309(clause)
        v308 = check_clause_against_308(clause)
        flags = check_general_red_flags(clause)

        violations = v309.get("violations", []) if "error" not in v309 else []
        suspicions = v308.get("suspicions", []) if "error" not in v308 else []
        red_flags = flags.get("red_flags", []) if "error" not in flags else []

        if violations or suspicions or red_flags:
            if violations:
                verdict = "unwirksam"
                n_unwirksam += 1
            elif suspicions:
                verdict = "wahrscheinlich_unwirksam"
                n_wahrscheinlich += 1
            else:
                verdict = "kontextabhängig"
                n_red_flag += 1

            problematic.append(
                {
                    "clause_index": i,
                    "clause_excerpt": clause[:200] + ("…" if len(clause) > 200 else ""),
                    "verdict": verdict,
                    "violations": violations,
                    "suspicions": suspicions,
                    "red_flags": red_flags,
                }
            )

    return {
        "clause_count": len(clauses),
        "problematic_count": len(problematic),
        "summary": {
            "unwirksam_count": n_unwirksam,
            "wahrscheinlich_unwirksam": n_wahrscheinlich,
            "red_flag_count": n_red_flag,
        },
        "problematic_clauses": problematic,
    }


# ── Tool 5: generate_widerspruch ─────────────────────────────────────


@mcp.tool()
@traced("generate_widerspruch")
def generate_widerspruch(
    problematic_clauses: list[dict[str, Any]],
    sender_name: str,
    counterparty_name: str = "",
    contract_reference: str = "",
) -> dict[str, Any]:
    """
    Generate a German "die folgenden AGB-Klauseln sind unwirksam" Widerspruch letter
    based on the output of analyze_agb. Cites each problematic clause + the § that
    invalidates it.

    Args:
      problematic_clauses: the `problematic_clauses` list from analyze_agb output.
      sender_name:         your name.
      counterparty_name:   the company whose AGB are problematic (optional).
      contract_reference:  e.g. "Vertrag Nr. 12345, abgeschlossen am 15.08.2024" (optional).

    Returns:
      {"letter_markdown": "<full German letter>", "cited_paragraphs": [...]}
    """
    if not sender_name.strip():
        return error_envelope("invalid_input", "sender_name is required")
    if not problematic_clauses:
        return error_envelope(
            "invalid_input", "problematic_clauses list is empty — nothing to challenge"
        )

    cited: set[str] = set()
    body_lines = []
    for i, pc in enumerate(problematic_clauses, 1):
        excerpt = pc.get("clause_excerpt", "")[:300]
        body_lines.append(f"\n## Klausel {i}\n")
        body_lines.append(f"> {excerpt}\n")
        for v in pc.get("violations", []):
            cited.add(v["paragraph"])
            body_lines.append(
                f"- **Unwirksam per {v['paragraph']}** ({v['title']}): {v['rule'][:200]}..."
            )
        for s in pc.get("suspicions", []):
            cited.add(s["paragraph"])
            body_lines.append(
                f"- **Wahrscheinlich unwirksam per {s['paragraph']}** ({s['title']}): "
                f"Kontextabhängig zu prüfen."
            )
        for rf in pc.get("red_flags", []):
            cited.add(rf["paragraph"])
            body_lines.append(f"- **Bedenken per {rf['paragraph']}**: {rf['explanation']}")

    cited_block = ", ".join(sorted(cited)) if cited else "siehe oben"
    cp_block = f"\n\n**An:** {counterparty_name}" if counterparty_name else ""
    ref_block = f"\n\n**Bezug:** {contract_reference}" if contract_reference else ""

    letter = f"""# Widerspruch gegen einzelne AGB-Klauseln{cp_block}{ref_block}

Sehr geehrte Damen und Herren,

ich, **{sender_name}**, widerspreche hiermit ausdrücklich den folgenden Klauseln
Ihrer Allgemeinen Geschäftsbedingungen, die nach meiner Auffassung gegen das
BGB AGB-Recht verstoßen und somit unwirksam sind ({cited_block}):
{"".join(body_lines)}

Ich fordere Sie auf, mir innerhalb von **14 Tagen** zu bestätigen, dass Sie
diese Klauseln Ihnen gegenüber nicht anwenden werden.

Ohne Bestätigung gehe ich davon aus, dass Sie die Unwirksamkeit anerkennen —
und behalte mir gerichtliche Schritte ausdrücklich vor (insbesondere
Unterlassungsantrag nach UKlaG, falls Sie diese Klauseln weiter in Verträgen
mit anderen Verbrauchern verwenden).

Mit freundlichen Grüßen

{sender_name}
"""

    return {
        "letter_markdown": letter.strip(),
        "cited_paragraphs": sorted(cited),
        "clause_count": len(problematic_clauses),
    }


# ── Entry point ─────────────────────────────────────────────────────


def main() -> None:
    configure_logging(logger_name="agb_reader_mcp")
    run_main(mcp)


if __name__ == "__main__":
    main()
