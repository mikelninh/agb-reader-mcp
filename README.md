# agb-reader-mcp

**German Terms-of-Service (AGB) clause checker — detects unfair clauses against BGB §§ 305c / 307 / 308 / 309 with verifiable § citations.**

[![Tests](https://img.shields.io/badge/tests-25%2F25-brightgreen?logo=pytest)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-server-blue)](https://modelcontextprotocol.io)
[![Built with civic-ai-mcp-toolkit](https://img.shields.io/badge/built_with-civic--ai--mcp--toolkit-blueviolet)](https://github.com/mikelninh/civic-ai-mcp-toolkit)

---

## What it does

Paste an AGB block. Get back every problematic clause with the § that invalidates it.

| You ask Claude… | …agb-reader-mcp answers |
|---|---|
| "Lies diese AGB — was ist problematisch?" | Liste aller Klauseln mit Verstoß gegen § 309, § 308, § 305c, § 307 — jeweils mit Rechtstext + Erklärung |
| "Ist 'Aufrechnung ausgeschlossen' zulässig?" | **Unwirksam per § 309 Nr. 3 BGB** — Aufrechnungsverbot bei unbestrittenen Forderungen verboten |
| "Was sagst du zu 'Gerichtsstand ist München'?" | **Wahrscheinlich überraschend per § 305c BGB** — Verbraucher klagen am Wohnsitz |
| "Schreib mir den Widerspruch." | Vollständiger deutscher Widerspruchsbrief mit § -Zitaten + 14-Tage-Frist + UKlaG-Hinweis |

---

## Why this exists

**Niemand liest AGB.** Studien: <1% öffnet die AGB-Seite, <0.1% liest tatsächlich. Verständlich — typische AGB sind 8.000-25.000 Wörter, juristisch, voller Verweise. **Ergebnis:** schräge Klauseln rutschen durch. Einseitige Preisänderung, Pauschal-Stornos, Aufrechnungsverbote, Gerichtsstand 600 km vom Wohnort. Alle illegal — aber nur, wenn jemand es bemerkt.

`agb-reader-mcp` macht diese Erkennung automatisch. Pattern-Matching gegen den vollständigen BGB-Klauselverbot-Katalog (§§ 308 + 309) und Verbraucherzentrale-typische Red-Flags. Jede Erkennung kommt mit § -Zitat + Rechtstext + Erklärung — auditierbar.

Das gehört in **jedes Browser-Frontend** als 1-Klick-Check beim Einkauf. Dieser MCP ist die Engine; ein Chrome-Extension-Frontend ist nächstes Wochenende.

---

## Tools exposed

| Tool | Purpose |
|---|---|
| `check_clause_against_309(clause_text)` | Single-Klausel-Check gegen § 309 BGB — die 13 absoluten Klauselverbote (Verdict: unwirksam) |
| `check_clause_against_308(clause_text)` | Check gegen § 308 BGB — 8 Klauseltypen mit Wertungsspielraum (Verdict: wahrscheinlich unwirksam) |
| `check_general_red_flags(clause_text)` | Verbraucherzentrale-style Catch: Gerichtsstand, Rechtswahl, AGB-Änderungsvorbehalt, intransparent, Vorab-Werbeeinwilligung |
| `analyze_agb(agb_text, max_clauses)` | Volle Pipeline: split → check all → consolidated report |
| `generate_widerspruch(problematic_clauses, sender_name, ...)` | Deutscher Widerspruchsbrief mit § -Zitaten + 14-Tage-Frist + UKlaG-Hinweis |

---

## Quickstart — Claude Desktop in one minute

```bash
git clone https://github.com/mikelninh/agb-reader-mcp
cd agb-reader-mcp
pip install -e .
```

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "agb-reader": {
      "command": "agb-reader-mcp"
    }
  }
}
```

Or register with Claude Code instead:

```bash
claude mcp add agb-reader -- agb-reader-mcp
```

Restart Claude Desktop. Try:

> *"Hier sind die AGB von [Anbieter X]: [text]. Welche Klauseln sind problematisch und warum?"*

**No API key needed.** All five tools work fully offline.

---

## Test coverage

```
25 passed in <1s
```

- 8 § 309 detection tests (Aufrechnung, Haftung, Körperverletzung, Vertragsstrafe, Einschreiben, Nachweis-Ausnahme, …)
- 3 § 308 detection tests (Änderungsvorbehalt, fingierte Zustimmung, „solange Vorrat reicht")
- 5 Red-Flag-Tests (Gerichtsstand, AGB-Änderung, intransparent, Werbeeinwilligung, unschuldig)
- 4 analyze_agb pipeline tests (mehrere Verstöße, leerer Input, Max-Cap, Excerpts)
- 4 Widerspruch-Tests
- 1 JSON-Serialisierbarkeit über alle Tools

---

## Honest limits

- **Pattern-Matching ≠ Volljurist.** Fängt typische und offensichtliche Verstöße. Versteckte / kreative Formulierungen rutschen durch.
- **§ 305c / § 307 sind kontextabhängig.** Wir flaggen Muster — Endurteil bleibt Einzelfall.
- **B2B vs. B2C nicht unterschieden.** Manche § 309-Verbote gelten nur gegenüber Verbrauchern.
- **Catalog ist Stand 2026.** Neue BGH-Rechtsprechung via PR.
- **Keine Pre-Check der AGB-Einbeziehung** (§ 305 Abs. 2 BGB).

---

## Part of an MCP-server portfolio

Built on [civic-ai-mcp-toolkit](https://github.com/mikelninh/civic-ai-mcp-toolkit). ~400 Zeilen Substanzcode, Rest aus dem Toolkit.

Sibling MCPs:
- [gitlaw-mcp](https://github.com/mikelninh/gitlaw) · [safevoice-mcp](https://github.com/mikelninh/safevoice) · [pmm-mcp](https://github.com/mikelninh/pmm-mcp) · [elterngeld-mcp](https://github.com/mikelninh/elterngeld-mcp) · [flight-rights-mcp](https://github.com/mikelninh/flight-rights-mcp) · [judge-mcp](https://github.com/mikelninh/judge-mcp) · [grailsense](https://github.com/mikelninh/grailsense)

Composition pattern: agb-reader-mcp kann **gitlaw-mcp** für die BGB-Volltexte hinter jedem zitierten § aufrufen — keine Halluzination möglich.

---

## Roadmap

- [ ] **Chrome extension frontend** — markiere AGB → 1-Klick-Check → Popup mit Red-Flags
- [ ] Compose mit gitlaw-mcp für vollen BGB-Paragraph-Lookup
- [ ] Compose mit judge-mcp zur Bewertung ganzer AGB-Sets
- [ ] English version (UK Consumer Rights Act 2015)
- [ ] B2B/B2C automatische Klassifikation
- [ ] PDF-Input-Support
- [ ] BGH-Update-Pipeline (2024/2025 Cookie-Banner, AGB-Buttons)

---

## License

MIT.
