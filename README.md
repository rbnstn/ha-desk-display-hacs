# Desk Display für Home Assistant

HACS-Integration für ein E32R35T-Display mit der Desk-Display-Firmware.
Version **0.1.1**, Home Assistant **2026.9 oder neuer**.

## Installation über HACS

1. **HACS → Drei-Punkte-Menü → Benutzerdefinierte Repositories** öffnen.
2. `https://github.com/rbnstn/ha-desk-display-hacs` eintragen und Typ
   **Integration** auswählen.
3. **Desk Display** suchen und **Herunterladen** wählen.
4. Home Assistant neu starten und die Oberfläche mit **Strg + F5** neu laden.
5. Bei einer neuen Einrichtung: **Einstellungen → Geräte & Dienste →
   Integration hinzufügen → Desk Display**. Display-IP und Geräteschlüssel eingeben.

Bei einer vorhandenen manuellen Installation dieselben Schritte ausführen.
Die bestehende HA-Integration nicht löschen: Geräteeinrichtung und gespeicherte
Layouts bleiben erhalten. Ein erneutes Flashen ist für diesen Wechsel nicht nötig.
Weitere Updates werden über HACS heruntergeladen; anschließend HA neu starten.

## Anzeige gestalten

Im Seitenleisten-Panel **Desk Display** lassen sich bis zu acht Texte oder
HA-Werte positionieren und Schriftgröße sowie Farben anpassen.
**Speichern & übertragen** speichert das Layout und zeigt es auf dem Display.
Änderungen ausgewählter HA-Werte aktualisieren Display und Vorschau automatisch.
Die Verbindung wird zusätzlich alle zehn Sekunden geprüft.

Der MVP unterstützt eine Seite pro Display. Kamerastream, Touch-Buttons,
Switches und Klingelansicht sind noch nicht enthalten.

## Display-Firmware

Das Display braucht die passende Desk-Display-Firmware und muss über WLAN
von HA erreichbar sein. Dieses Repository verteilt ausschließlich die
HA-Integration; Firmware und deren Entwicklung werden separat verwaltet.
Die Hersteller-Demo ist nicht kompatibel. HACS flasht keine ESP32-Firmware.

## Kommunikation und Support

Die Integration nutzt die vorhandenen HA-Entitäten und kommuniziert lokal
mit dem Display auf Port 80. Der Geräteschlüssel wird in HA gespeichert.
Keine HA-Zugangsdaten werden auf das Display übertragen. Das Display ist
für das Heimnetz vorgesehen; Port 80 nicht ins Internet weiterleiten.

Fehler können unter [Issues](https://github.com/rbnstn/ha-desk-display-hacs/issues)
gemeldet werden. Bitte keine Passwörter, Geräteschlüssel oder HA-Tokens posten.

Dies ist das öffentliche Installationsrepository. Die Entwicklung und Tests
finden in einem separaten privaten Repository statt. Es werden nur ausgewählte
Integrationsdateien veröffentlicht, keine private Entwicklungshistorie.
