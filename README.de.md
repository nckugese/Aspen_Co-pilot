# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · **Deutsch** · [Français](README.fr.md) · [Русский](README.ru.md)

Dies ist eine Übersetzung; bei Abweichungen gilt die [englische Fassung](README.md).

**Lassen Sie einen KI-Agenten chemische Prozesse in Ihrem eigenen Aspen Plus entwerfen,
simulieren und optimieren – Sie sehen jeden Schritt und behalten die Kontrolle.**

Aspen Co-pilot verbindet Aspen Plus über das Model Context Protocol (MCP) mit KI-Agenten wie
Claude Code und Codex. Sie beschreiben den Prozess in natürlicher Sprache; der Agent erledigt
die Arbeit in Aspen, und Sie prüfen das Ergebnis.

Nur für Windows. Sie benötigen eine eigene lizenzierte Aspen-Plus-Installation; dieses Projekt
enthält sie nicht. Entwickelt vom NCKU GESE Lab.

## Was es kann

**Prozesse aufbauen und ändern.** Erstellen Sie ein Fließbild aus einer Beschreibung –
Komponenten, Stoffdatenmethoden, Reaktionen, Grundoperationen und Ströme –, setzen und
justieren Sie beliebige Parameter, starten Sie die Simulation und lesen Sie die Ergebnisse aus.
Die meisten Funktionen von Aspen Plus stehen zur Verfügung.

**Von der Literatur zum lauffähigen Modell.** Mit den Recherchewerkzeugen Ihres KI-Clients kann
der Agent Kinetik, Betriebsbedingungen und Verfahrensrouten aus Veröffentlichungen und Patenten
zusammentragen und daraus ein Aspen-Modell bauen, das Sie mit den Quellen abgleichen können.

**Herausfinden, warum eine Simulation scheitert.** Es prüft vor dem Lauf, was Aspen noch fehlt,
erklärt fehlgeschlagene Läufe und Warnungen und behebt sie. Erfolgreiche Lösungen werden für das
nächste Mal auf Ihrem Rechner gespeichert.

**Den Prozess optimieren.** Neun Algorithmen hinter einem Werkzeug – NSGA-II, NSGA-III, PSO,
DE/GDE3, Gradientenverfahren (SLSQP), Rastersuche und drei Bayes'sche Verfahren (BO, CBO,
AFM-CBO) – für ein- oder mehrkriterielle Probleme mit Nebenbedingungen, dazu Pinch-Analyse und
Vorschläge für Wärmeübertrager-Paarungen zur Wärmeintegration.

**Nachschlagen statt raten.** Eine Referenz für jeden Block, jeden Strom und jede Einstellung
([aspen-mcp/docs](aspen-mcp/docs/aspen.md)), die der Agent konsultiert, bevor er ein Feld ändert.

## Für die Zusammenarbeit mit Menschen gebaut

Einem LLM-Agenten, der Software selbstständig bedient, ist schwer zu vertrauen: Sie sehen nicht,
was er geändert hat oder warum, und können einen Fehler nicht stoppen, bevor er im Modell landet.
Aspen Co-pilot schließt diese Lücke mit der **Aspen Workbench**, einem Desktop-Fenster neben
Aspen Plus.

- **Sehen, was die KI tut.** Das Fließbild, die Ergebnisse und jede Änderung der KI samt
  Begründung werden live aktualisiert. Machen Sie jede Änderung rückgängig oder kehren Sie zu
  einem Wiederherstellungspunkt zurück.
- **Die Kontrolle behalten.** Im Prüfmodus warten die Änderungen der KI auf Ihre Freigabe;
  größere Änderungen kommen als Vorschläge, die nur Sie ausführen können.
- **Die Arbeit selbst festlegen – mit Blockprogrammen.** Stellen Sie Parameterstudien,
  Berechnungen, Tabellen, Diagramme und Optimierungsstudien – mit Ihren eigenen Variablen,
  Zielen und Nebenbedingungen – per Drag-and-drop aus Blöcken zusammen, ganz ohne Code. Die KI
  kann ein Programm schreiben, das Sie bearbeiten, oder Ihres ausführen.
- **Zusammenarbeiten.** Klicken Sie auf einen beliebigen Strom oder Block und fragen Sie per
  **Ask AI** danach. Im Lernmodus erklärt die KI das verfahrenstechnische Prinzip hinter jeder
  Änderung.

Die Workbench hat eine englische und eine chinesische Oberfläche (Deutsch wird nicht angeboten)
und läuft auch ohne KI-Client (`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`: kein Netzwerk,
keine Tokens).

## Installation

Sie benötigen **Windows**, ein lizenziertes **Aspen Plus** und **[uv](https://docs.astral.sh/uv/)**
(`winget install --id=astral-sh.uv -e`; es bringt sein eigenes Python mit).

**Claude Code:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex:** `codex plugin marketplace add nckugese/Aspen_Co-pilot`, dann **Aspen Plus** unter
`/plugins` aktivieren und seinen Hooks unter `/hooks` vertrauen.

Starten Sie den Client anschließend neu. In der ersten Sitzung bietet er an, die Einrichtung
abzuschließen (etwa 200 MB: Python, der Server und die Optimierungsbibliotheken); stimmen Sie zu
und starten Sie noch einmal neu. `/aspen-doctor` prüft das Ergebnis.

Das Plugin ist auf ein Release festgelegt, daher ändert sich nichts, bis Sie es aktualisieren
(`claude plugin update aspen-plus@aspen-mcp`); es meldet sich, wenn ein neueres Release
verfügbar ist.

Andere MCP-Clients (Claude Desktop, Gemini CLI, Codex ohne das Plugin), die
Schritt-für-Schritt-Anleitung mit Prüfungen und Fehlerbehebung: **[INSTALL.md](INSTALL.md)** (Englisch).

## Datenschutz

Alles, was der Server speichert, bleibt auf Ihrem Rechner unter `~/.aspen-mcp/`: sein Log, das
Änderungsjournal, Wiederherstellungspunkte (Kopien Ihrer Modelle) und Ihr Fehlerverlauf. Ihre
Modelle, Ergebnisse und Unterhaltungen werden von diesem Projekt nirgendwohin gesendet. Netzwerk
wird nur hierfür genutzt:

- die Update-Prüfung des Plugins, höchstens einmal täglich (`git ls-remote` gegen dieses Repository);
- der erste Aufruf von `pinch_analysis`, der Python 3.14 und OpenPinch über uv herunterlädt;
- Installation und Aktualisierung, die den Server und seine Abhängigkeiten über uv abrufen.

Was Ihr KI-Client an seinen eigenen Anbieter sendet, regelt dieser Client.

## Feedback

Fragen und Fehlermeldungen: [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues). Sicherheitsmeldungen: [SECURITY.md](SECURITY.md) (Englisch).

## Lizenz

MIT – siehe [LICENSE](LICENSE). Copyright (c) 2026 NCKU GESE Lab.

Wenn Sie diese Software in wissenschaftlichen Arbeiten verwenden, zitieren Sie bitte dieses Repository.

## Haftungsausschluss

Aspen Plus® und AspenTech® sind Marken von Aspen Technology, Inc. Dieses Projekt ist eine
unabhängige, inoffizielle Integration und steht in keiner Verbindung zu Aspen Technology, Inc.
und wird von Aspen Technology, Inc. weder unterstützt noch gesponsert. Es enthält oder vertreibt
Aspen Plus nicht; es steuert eine separate, vom Benutzer bereitgestellte Installation, und Sie
benötigen eine eigene gültige Aspen-Plus-Lizenz.
