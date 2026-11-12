# Buttons

Es gibt genau drei Button-Varianten. Schrift ist immer die der Seite, `font-weight: 600`, Eckenradius `5px` (`--radius`).

## Primary

Rot-pink gefüllt, weiße Schrift, kein Rahmen. Nur für die Hauptaktion einer Seite bzw. eines Dialogs.

| | |
| --- | --- |
| Hintergrund | `#ff0350` (`--accent`) |
| Schrift | `#ffffff` |
| Rahmen | keiner |

Beispiele: Einloggen, Registrieren, Beitreten, Gruppe erstellen, Speichern, Kopieren, „Zur Gruppe", „Neuen Link erzeugen", „Teil-Zusage speichern".

## Secondary

Grau gefüllt, schwarze Schrift, kein Rahmen. Für neutrale Nebenaktionen und Navigation.

| | |
| --- | --- |
| Hintergrund | `#f0f4f7` (`--surface`) |
| Schrift | `#000000` (`--text`) |
| Rahmen | keiner |
| Hover | `#dbe2e8` |

Beispiele: Abbrechen, Einstellungen, Zurück (zum Kalender), „Nicht beitreten". Die Wochen-/Monatsumschaltung im Kalender ist ein graues Segment, der aktive Eintrag darin solid gefüllt (Primary-Rot).

## Danger (rot umrandet)

Weißer bzw. transparenter Hintergrund, roter Rahmen, rote Schrift — derselbe Rotton wie Primary (`#ff0350`), damit nie zwei Rottöne nebeneinander stehen. Alle Danger-Buttons hängen an der Variable `--danger`.

| | |
| --- | --- |
| Hintergrund | `#ffffff` bzw. transparent |
| Schrift | `#ff0350` (`--danger`) |
| Rahmen | `1px solid #ff0350` |

Beispiele: Absagen, Löschen (Termin), Entfernen (Mitglied), Gruppe verlassen, Gruppe löschen, Konto löschen, „Termine löschen", „Fällt aus". Ausnahme: „Ja" im Bestätigungs-Dialog ist solid rot gefüllt.

## Neutral-Outline (nur in Dialogen)

Transparent, grauer Rahmen (`--line`), schwarze Schrift. Für nicht-destruktive Aktionen neben einem Danger-Button.

Beispiele: „Teilweise" im Termin-Dialog. „Zusagen" ist dagegen Primary, „Absagen" Danger — im Teilnahme-Bereich des Termin-Dialogs stehen also nie zwei Primaries nebeneinander. „Findet statt" nutzt das Konsens-Grün (`--success`) und ist im gewählten Zustand (`is-chosen`) grün gefüllt.

## Termin-Dialog

Zwei Modi: Der Ersteller sieht die bearbeitbaren Felder mit „Löschen" (Danger), „Abbrechen" (Secondary) und „Speichern" (Primary) — der Teilnahme-Bereich ist ihm verborgen, weil er implizit zusagt. Alle anderen sehen read-only-Felder, nur „Schließen" (Secondary) und den Teilnahme-Bereich mit „Zusagen" (Primary), „Teilweise" (Secondary), „Absagen" (Danger).
