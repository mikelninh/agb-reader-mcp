"""agb-reader-mcp tests — hermetic, no network. Pin the catalog detection contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agb_reader_mcp.server import (  # noqa: E402
    analyze_agb,
    check_clause_against_308,
    check_clause_against_309,
    check_general_red_flags,
    generate_widerspruch,
)


# ── § 309 detection (Klauselverbote OHNE Wertung) ────────────────────


def test_309_aufrechnungsverbot_detected():
    r = check_clause_against_309("Die Aufrechnung gegen unsere Forderungen ist ausgeschlossen.")
    assert r["violation_count"] >= 1
    nrs = [v["nr"] for v in r["violations"]]
    assert "3" in nrs
    assert r["verdict"] == "unwirksam"


def test_309_haftungsausschluss_grobe_fahrlässigkeit_detected():
    r = check_clause_against_309("Unsere Haftung ist ausgeschlossen, soweit kein Vorsatz vorliegt.")
    assert r["violation_count"] >= 1
    titles = [v["title"] for v in r["violations"]]
    assert any("Vorsatz" in t or "Verschulden" in t for t in titles)


def test_309_haftung_bei_körperverletzung_detected():
    r = check_clause_against_309(
        "Eine Haftung für Schäden aus der Verletzung des Körpers oder der Gesundheit ist ausgeschlossen."
    )
    assert r["violation_count"] >= 1


def test_309_vertragsstrafe_detected():
    r = check_clause_against_309(
        "Bei Nichtabnahme der Ware ist eine Vertragsstrafe von 30% des Kaufpreises zu zahlen."
    )
    nrs = [v["nr"] for v in r["violations"]]
    assert "6" in nrs


def test_309_einschreiben_kündigung_detected():
    r = check_clause_against_309("Die Kündigung kann nur per Einschreiben erfolgen.")
    nrs = [v["nr"] for v in r["violations"]]
    assert "13" in nrs


def test_309_pauschalierter_schaden_with_nachweis_exception():
    """Pauschale OK wenn Nachweis geringerer Schaden zugelassen."""
    r = check_clause_against_309(
        "Bei Zahlungsverzug wird ein pauschalierter Schadensersatz von €40 berechnet. "
        "Dem Kunden bleibt der Nachweis eines geringeren Schadens unbenommen."
    )
    # § 309 Nr 5 should NOT trigger because of the Nachweis exception
    nrs = [v["nr"] for v in r["violations"]]
    assert "5" not in nrs


def test_309_innocent_clause_no_violations():
    r = check_clause_against_309("Der Vertrag tritt mit beiderseitiger Unterschrift in Kraft.")
    assert r["violation_count"] == 0
    assert r["verdict"] == "wahrscheinlich_zulässig"


def test_309_empty_input_returns_error():
    r = check_clause_against_309("")
    assert r.get("error") == "invalid_input"


# ── § 308 detection (Klauselverbote MIT Wertung) ─────────────────────


def test_308_änderungsvorbehalt_detected():
    r = check_clause_against_308(
        "Wir behalten uns vor, die versprochene Leistung jederzeit zu ändern."
    )
    nrs = [s["nr"] for s in r["suspicions"]]
    assert "4" in nrs


def test_308_fingierte_zustimmung_detected():
    r = check_clause_against_308(
        "Wenn Sie nicht innerhalb von 14 Tagen widersprechen, gilt Ihre Zustimmung als erteilt."
    )
    nrs = [s["nr"] for s in r["suspicions"]]
    assert "5" in nrs


def test_308_solange_vorrat_detected():
    r = check_clause_against_308("Lieferung erfolgt, solange der Vorrat reicht.")
    nrs = [s["nr"] for s in r["suspicions"]]
    assert "8" in nrs


# ── general red flags (§ 305c / § 307) ───────────────────────────────


def test_redflag_gerichtsstandsklausel():
    r = check_general_red_flags("Ausschließlicher Gerichtsstand ist München.")
    cats = [f["category"] for f in r["red_flags"]]
    assert "gerichtsstand" in cats


def test_redflag_einseitige_agb_änderung_detected():
    r = check_general_red_flags("Wir behalten uns vor, diese AGB jederzeit zu ändern.")
    cats = [f["category"] for f in r["red_flags"]]
    assert "agb_änderungsklausel" in cats


def test_redflag_intransparent_im_zumutbaren_rahmen():
    r = check_general_red_flags(
        "Der Kunde gewährt im zumutbaren Rahmen Zugang zu den Räumlichkeiten."
    )
    cats = [f["category"] for f in r["red_flags"]]
    assert "intransparenz" in cats


def test_redflag_pauschale_werbeeinwilligung():
    r = check_general_red_flags(
        "Mit Vertragsschluss erklärt sich der Kunde mit Werbung per Newsletter einverstanden."
    )
    cats = [f["category"] for f in r["red_flags"]]
    assert "datenschutz_pauschalvergabe" in cats


def test_redflag_innocent_clause_no_flags():
    r = check_general_red_flags("Der Mindestbestellwert beträgt 10 Euro.")
    assert r["red_flag_count"] == 0


# ── analyze_agb (full pipeline) ──────────────────────────────────────


_SAMPLE_BAD_AGB = """
§ 1 Geltungsbereich
Diese AGB gelten für alle Verträge mit Verbrauchern.

§ 2 Preise
Die Preise können jederzeit angepasst werden.

§ 3 Lieferung
Lieferung erfolgt, solange der Vorrat reicht. Eine Lieferfrist von bis zu 90 Tagen wird vereinbart.

§ 4 Haftung
Unsere Haftung ist ausgeschlossen, außer bei Vorsatz.
Eine Haftung für Schäden aus der Verletzung des Körpers ist ausgeschlossen.

§ 5 Kündigung
Die Kündigung kann nur per Einschreiben erfolgen.
Die Mindestlaufzeit beträgt 3 Jahre.

§ 6 Aufrechnung
Die Aufrechnung ist ausgeschlossen.

§ 7 Gerichtsstand
Ausschließlicher Gerichtsstand ist Berlin.
"""


def test_analyze_agb_finds_multiple_issues_in_bad_sample():
    r = analyze_agb(_SAMPLE_BAD_AGB)
    assert r["clause_count"] > 3
    assert r["problematic_count"] >= 4
    # We expect § 309 hits across multiple clauses
    assert r["summary"]["unwirksam_count"] >= 3
    # Plus red-flag for Gerichtsstand
    assert r["summary"]["red_flag_count"] >= 1


def test_analyze_agb_empty_input_returns_error():
    r = analyze_agb("")
    assert r.get("error") == "invalid_input"


def test_analyze_agb_max_clauses_cap_respected():
    """Synthesise a long AGB and assert the cap holds."""
    big_text = "\n\n".join(
        f"§ {i} Klausel\nDie Aufrechnung ist ausgeschlossen." for i in range(1, 250)
    )
    r = analyze_agb(big_text, max_clauses=50)
    assert r["clause_count"] <= 50


def test_analyze_agb_returns_clause_excerpts():
    r = analyze_agb(_SAMPLE_BAD_AGB)
    for pc in r["problematic_clauses"]:
        assert "clause_excerpt" in pc
        assert len(pc["clause_excerpt"]) > 0


# ── generate_widerspruch ─────────────────────────────────────────────


def test_widerspruch_letter_lists_each_clause_and_cites_paragraph():
    analysis = analyze_agb(_SAMPLE_BAD_AGB)
    letter_result = generate_widerspruch(
        problematic_clauses=analysis["problematic_clauses"],
        sender_name="Anna Müller",
    )
    assert "Anna Müller" in letter_result["letter_markdown"]
    # Cited paragraphs should include § 309 references
    paragraphs = " ".join(letter_result["cited_paragraphs"])
    assert "§ 309" in paragraphs


def test_widerspruch_missing_sender_rejected():
    r = generate_widerspruch(problematic_clauses=[{"clause_excerpt": "x"}], sender_name="")
    assert r.get("error") == "invalid_input"


def test_widerspruch_empty_clauses_rejected():
    r = generate_widerspruch(problematic_clauses=[], sender_name="X")
    assert r.get("error") == "invalid_input"


def test_widerspruch_includes_counterparty_when_provided():
    analysis = analyze_agb(_SAMPLE_BAD_AGB)
    r = generate_widerspruch(
        problematic_clauses=analysis["problematic_clauses"],
        sender_name="Anna Müller",
        counterparty_name="Beispiel GmbH",
    )
    assert "Beispiel GmbH" in r["letter_markdown"]


# ── JSON-serialisability ─────────────────────────────────────────────


def test_all_tool_returns_are_json_serialisable():
    json.dumps(check_clause_against_309("Die Aufrechnung ist ausgeschlossen."))
    json.dumps(check_clause_against_308("Wir behalten uns Änderungen vor."))
    json.dumps(check_general_red_flags("Gerichtsstand ist München."))
    analysis = analyze_agb(_SAMPLE_BAD_AGB)
    json.dumps(analysis)
    json.dumps(
        generate_widerspruch(
            problematic_clauses=analysis["problematic_clauses"],
            sender_name="Test",
        )
    )
