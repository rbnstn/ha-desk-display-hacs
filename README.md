# Desk Display für Home Assistant

[English](README.en.md) · [Installation](#installation) · [Firmware & Releases](https://github.com/rbnstn/ha-desk-display-hacs/releases) · [Hinweise & Automationen](docs/AUTOMATIONS.md)

**Dein Home-Assistant-Dashboard auf einem kleinen Touchdisplay.** Werte, Energieflüsse, Schalter, Wetter und Kameras lassen sich im visuellen Designer zusammenstellen. Home Assistant rendert die Anzeige; die ESP32-Firmware empfängt nur Bilddaten und meldet Berührungen zurück.

| Dashboard mit Werten und Touchbedienung | Energiefluss mit Batterie und Auto |
| :---: | :---: |
| ![Dashboard mit Temperatur, Solarleistung, Licht und Abendmodus](docs/images/dashboard.png) | ![Energiefluss mit Solar, Batterie, Wallbox und Auto-Ladestand](docs/images/energy.png) |

*Diese Bilder stammen aus dem tatsächlichen Renderer mit Beispielwerten. Sie sind keine Fotos eines physischen Geräts. Das Projekt wird aktiv entwickelt; die Geräteunterstützung ist auf das E32R35T begrenzt.*

## Was kann das Projekt?

| Bereich | Funktionen |
| --- | --- |
| Designer | Ziehen, Größe ändern, Raster, Einrasten an Kanten und Mittelpunkten, Abstandsanzeigen, Mehrfachauswahl, Gruppen, gleiche Abstände, Rückgängig/Wiederholen, Sperren und Ausblenden |
| Texte und Werte | Links/mittig/rechts ausrichten, automatische Schriftanpassung, Formatvorlagen, W/kW-Umschaltung, Nachkommastellen, Komma/Punkt, eigene Einheiten und Ersatzsensoren |
| Energie | Solar, Haus, Bezug/Einspeisung, Batterie laden/entladen, Batteriestand; optionale Wallbox, Auto-Ladestand, Ladeziel und Restladezeit |
| Bedienung | Touchbuttons, Schalter, Schieberegler, Mediensteuerung, langes Drücken und optionale Bestätigung |
| Weitere Elemente | Uhrzeit, Datum, Bilder, HA-Icons, Verlauf, Fortschritt, Ringanzeigen, Statuschips, Energiekosten, Wetter und Countdown |
| Seiten | Bis zu vier Seiten mit je zehn Elementen; Touchnavigation, Wischen, Rotation und bedingte Seitenwechsel |
| Klingel | Kamera, Türöffner, Türstatus, eigene Klingelansicht, Kameravorbereitung und begrenzter Klingelverlauf |
| Hinweise | Bis zu acht Regeln für Meldungen, Prioritäten, automatische Ausblendung; alternativ HA-Automationen |
| Vorlagen | Eingebaute Vorlagen, eigene Seiten und Komponenten, JSON-Import/Export, drei vorherige Layouts als Sicherung |
| Vorschau | Echte HA-Werte, Testzustände, gespeicherten Stand und Entwurf nebeneinander vergleichen |
| Gerät | Helligkeit, Nachtmodus, Ruhemodus, Diagnose, Firmwareupload über WLAN und gemeinsame Updateprüfung |

### Unterstützte Geräte

| Gerät / Voraussetzung | Unterstützung |
| --- | --- |
| **LCDWIKI E32R35T** | Unterstütztes Zielgerät: ESP32, 3,5 Zoll, 480 × 320 im Querformat, ST7796-Treiber und XPT2046-Touch |
| Andere ESP32-Displays | Keine fertige Firmware. Größe, Pinbelegung und Displaycontroller müssen ausdrücklich angepasst werden. |
| ESP32-8048S043 / GeekMagic-Geräte | Nicht mit dieser Firmware kompatibel. Ähnliche Gehäuse oder Namen bedeuten keine Kompatibilität. |
| Home Assistant | **2026.9 oder neuer**; automatisierte HA-Prüfung mit 2026.9.4 |
| Netzwerk | 2,4-GHz-WLAN; Home Assistant muss das Display lokal auf TCP-Port 80 erreichen können. |

Die Anzeige hat keinen Ton. Kamera-/Videofelder werden maximal einmal pro Sekunde aktualisiert. Das Projekt ersetzt kein Tablet und keine vollständige Lovelace-Oberfläche. HACS installiert die Integration, **nicht** die Displayfirmware.

## Installation

### 1. Firmware erstmals per USB installieren

Du brauchst ein E32R35T, ein USB-Datenkabel, Python 3.12 und Zugriff auf dessen seriellen Port.

1. Im [öffentlichen Repository](https://github.com/rbnstn/ha-desk-display-hacs) **Code → Download ZIP** wählen und entpacken. Alternativ mit Git klonen.
2. Ein Terminal im entpackten Projektordner öffnen.
3. PlatformIO installieren und die Firmware bauen und flashen:

```sh
python -m pip install "platformio==6.1.18"
python -m platformio run --project-dir firmware --target upload
```

Bei mehreren seriellen Geräten zusätzlich `--upload-port COM3` unter Windows beziehungsweise `--upload-port /dev/ttyUSB0` unter Linux verwenden. Den tatsächlichen Port einsetzen. Linux-Benutzer benötigen Zugriff auf den seriellen Port.

Details: [PlatformIO Upload-Befehl](https://docs.platformio.org/en/latest/core/userguide/cmd_run.html).

Falls der Upload nicht startet: BOOT gedrückt halten, RESET kurz drücken und BOOT beim Beginn des Uploads loslassen. Der erste PlatformIO-Upload schreibt auch Bootloader und Partitionstabelle. **Die einzelne Release-Datei `.bin` ist für spätere App-/OTA-Updates gedacht und ersetzt diesen vollständigen ersten USB-Upload nicht.**

Eine `secrets.h` ist für den öffentlichen Build nicht nötig. Die ursprüngliche Herstellerfirmware wird ersetzt.

### 2. WLAN am Display einrichten

1. Mit dem auf dem Display angezeigten WLAN **DeskDisplay-…** verbinden. Das dort angezeigte Passwort verwenden.
2. Im Browser **http://192.168.4.1** öffnen.
3. Name und Passwort deines 2,4-GHz-WLANs eintragen.
4. Den **Geräteschlüssel** aus dem Formular kopieren und sicher aufbewahren. Er wird später in Home Assistant benötigt.
5. Speichern und verbinden. Danach die lokale IP-Adresse des Displays im Router nachsehen und möglichst eine feste DHCP-Zuordnung einrichten.

WLAN erneut einrichten: BOOT etwa acht Sekunden halten und anschließend loslassen. Nach etwa drei Sekunden loslassen startet stattdessen die Touchkalibrierung. Die Einrichtung speichert Zugangsdaten lokal auf dem Gerät; öffentliche Firmware enthält keine WLAN-Daten.

### 3. Integration über HACS installieren

HACS muss bereits eingerichtet sein. Hilfe: [offizielle HACS-Anleitung](https://www.hacs.dev/docs/use/download/download/) und [benutzerdefinierte Repositories](https://www.hacs.dev/docs/faq/custom_repositories/).

1. HACS öffnen und unter **Benutzerdefinierte Repositories** diese URL hinzufügen:
   `https://github.com/rbnstn/ha-desk-display-hacs`
2. Kategorie **Integration** auswählen.
3. **Desk Display** herunterladen und Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Desk Display** öffnen.
5. Die lokale IP-Adresse ohne `http://` und den gespeicherten Geräteschlüssel eingeben. Ein automatisch entdecktes Display kann ebenfalls eingerichtet werden.
6. In der Seitenleiste **Desk Display** öffnen. Der Designer ist für HA-Administratoren sichtbar.

Manuelle Alternative: Den Ordner `custom_components/desk_display` nach `/config/custom_components/desk_display` kopieren und Home Assistant neu starten. Bei einem Wechsel zu HACS die bestehende Integration behalten.

### 4. Erste Anzeige erstellen

1. Im Designer das Display auswählen.
2. **Element hinzufügen** oder unter **Display → Vorlagen** eine Vorlage wählen.
3. HA-Sensoren und Aktionen zuordnen; Elemente ziehen und ihre Größe einstellen.
4. Unter **Aussehen** Farben, Ausrichtung und **Schrift automatisch anpassen** einstellen.
5. **Layout prüfen**, die Vorschau ansehen und **Speichern & übertragen** wählen.

Für den Energiefluss vier Leistungssensoren auswählen. Batterie-SOC und Auto-SOC benötigen Prozentwerte; Restladezeit unterstützt `s`, `min` oder `h`. Positive Netz-/Batteriewerte bedeuten Zufluss zum Haus, negative Einspeisung beziehungsweise Laden. Falls dein Sensor anders zählt, das Vorzeichen im Widget umkehren. Der Hausverbrauch wird direkt vom gewählten Sensor übernommen; Wallboxverbrauch wird nicht zusätzlich addiert.

Ohne Wallboxsensor erscheint kein Wallboxkreis. Ohne SOC-Sensor bleibt die Leistungsanzeige erhalten. Unbekannte Werte werden als fehlend angezeigt, nicht als erfundener Nullwert.

## Aktualisieren

- **Integration:** Update in HACS herunterladen, Home Assistant neu starten und den Designer neu laden. Bei veralteten Feldern am Mac `⌘ + Shift + R`, unter Windows/Linux `Strg + F5` verwenden.
- **Firmware:** Unter **Display → Firmware aktualisieren → Updates prüfen** installierte und verfügbare Versionen ansehen. Die passende E32R35T `.bin` vom [Release](https://github.com/rbnstn/ha-desk-display-hacs/releases) herunterladen, auswählen und installieren. WLAN-Updates setzen eine vorhandene Firmware ab 0.6.0 voraus. Bei älteren Versionen zuerst per USB aktualisieren.
- Firmware 0.9.0 unterstützt WLAN-Einrichtung und Ruhemodus. Die Integration 0.30.0 ergänzt die Designerfunktionen auf der HA-Seite; dafür ist kein neuer Firmwarestand nötig.
- Jeder veröffentlichte Integrationsrelease baut die Firmware automatisch und hängt `.bin`, SHA-256-Prüfsumme und Metadaten an. Die Firmwareversion kann bei mehreren Integrationsreleases gleich bleiben.

## Eigene Vorlagen, Meldungen und Sicherungen

Eigene Vorlagen werden unter **Display → Vorlagen** pro HA-Benutzer in diesem Browser gespeichert, maximal acht. Für einen anderen Browser als Datei exportieren und importieren. Seitenvorlagen ergänzen eine neue Seite, Komponenten ergänzen die aktuelle Seite. Geräte- und WLAN-Schlüssel sind nicht Bestandteil des Exports. Sensor-IDs und eigene Bilder können enthalten sein.

Unter **Display → Hinweise & Meldungen** Bedingungen für Fenster, Waschmaschine oder Stromverbrauch anlegen. Die Meldung erscheint beim Wechsel von falsch zu wahr und wird nach der eingestellten Dauer ausgeblendet. Beim Start bereits erfüllte Regeln werden nicht erneut gemeldet. Klingeln hat Vorrang. Beispiele für HA-Automationen stehen in [Deutsch und Englisch](docs/AUTOMATIONS.md).

![Energiefluss im hellen Design](docs/images/energy-light.png)

## Hilfe bei Problemen

| Problem | Prüfen |
| --- | --- |
| Display offline | WLAN, lokale IP, Geräteschlüssel und Erreichbarkeit von HA aus prüfen. IP über Integration **Neu konfigurieren** ändern. |
| Schwarzes oder falsches Bild nach Flashen | Exaktes Board E32R35T, vollständigen ersten USB-Upload und Stromversorgung prüfen. |
| Touch ungenau | BOOT etwa drei Sekunden halten und loslassen; Touchkalibrierung durchführen. |
| Neue Designerfelder fehlen | Installierte HACS-Version prüfen, HA neu starten, Browser vollständig neu laden. |
| Text zu groß | Automatische Schriftanpassung aktivieren oder einmalig verkleinern. Unter 12 px wird nicht verkleinert; dann das Element vergrößern. |
| Leistungswert falsch | HA-Einheit, Umrechnungsfaktor und Vorzeichen prüfen. Eigene Faktoren nur bewusst verwenden. |
| Kamera langsam | Maximal ein Videofeld pro Seite und höchstens ein Bild pro Sekunde; Netz und Kameravorbereitung prüfen. |
| Updateprüfung schlägt fehl | HA benötigt Internetzugriff auf GitHub. Später erneut versuchen oder den Release direkt öffnen. |

Das Display und HA kommunizieren im lokalen Netzwerk. Den Geräteport nicht ins Internet freigeben. Bedienelemente können reale HA-Aktionen auslösen; Vorschau und Simulation führen diese nicht aus.

## Entwicklung

Python-Tests, Chromium-Browsertests, aktuelle HA-Verträge, Firmware-Build und HACS-Prüfung laufen in CI. Automatisierte Prüfungen ersetzen noch keinen Test auf jedem physischen Gerät. Die README-Bilder sind mit `python tools/render_readme.py` im Entwicklungsrepository reproduzierbar. Entwicklung: [ha-desk-display](https://github.com/rbnstn/ha-desk-display), HACS/Firmware: [ha-desk-display-hacs](https://github.com/rbnstn/ha-desk-display-hacs).

Die Idee ist von [GeekMagic HACS](https://github.com/adrienbrault/geekmagic-hacs) inspiriert. Diese Implementierung ist eigenständig und enthält keinen kopierten GeekMagic-Code.
