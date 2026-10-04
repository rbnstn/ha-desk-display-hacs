# Desk Display für Home Assistant

HACS-Integration für ein E32R35T-Display mit der Desk-Display-Firmware.
Version **0.3.0**, Home Assistant **2026.9 oder neuer**.

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
HA-Werte, Buttons oder Switches positionieren und Schriftgröße sowie Farben anpassen.
**Speichern & übertragen** speichert das Layout und zeigt es auf dem Display.
Änderungen ausgewählter HA-Werte aktualisieren Display und Vorschau automatisch.
Die Verbindung wird zusätzlich alle zehn Sekunden geprüft.

**Element entfernen** neben **Element hinzufügen** löscht das ausgewählte Element.
Die Änderung mit **Speichern & übertragen** dauerhaft übernehmen.

Buttons unterstützen `button`, `input_button` und `script`; Switches unterstützen
`switch` und `input_boolean`. Aktionen werden nur durch Tippen am physischen Display
ausgelöst. Die Editor-Vorschau ist ausschließlich zum Gestalten.

Der MVP unterstützt eine Seite pro Display. Kamerastream und Klingelansicht
sind noch nicht enthalten.

## Display-Firmware

Das Display braucht die passende Desk-Display-Firmware und muss über WLAN
von HA erreichbar sein. Dieses Repository verteilt ausschließlich die
HA-Integration; Firmware und deren Entwicklung werden separat verwaltet.
Die Hersteller-Demo ist nicht kompatibel. HACS flasht keine ESP32-Firmware.

**Touch benötigt Firmware 0.2.0.** Nach dem Flashen die angezeigten Eckmarkierungen
antippen. Die Kalibrierung wird gespeichert. Für eine erneute Kalibrierung BOOT
am bereits laufenden Display drei Sekunden gedrückt halten, dann loslassen.
Ältere Firmware unterstützt weiterhin Texte und HA-Werte.

HA holt Touch-Ereignisse etwa einmal pro Sekunde ab. Jeder Druck löst höchstens
eine Aktion aus; lange gehaltene Berührungen werden nicht wiederholt. Veraltete
Ereignisse, andere Layoutversionen und nicht verfügbare Entitäten werden verworfen.
Eine wegen Verbindungsverlust oder Zeitüberschreitung unsichere Aktion wird nicht
automatisch wiederholt. Der Switch-Zustand kommt immer aus HA.

## Ruhigere Bildupdates und Debug-Anzeige (Firmware 0.3.0)

Neue Firmware empfängt ein komprimiertes Bild bzw. den geänderten Bildbereich
vollständig, bevor sie ihn über SPI zeichnet. Dadurch wird der Bildschirm nicht
mehr während des langsamen WLAN-Empfangs zeilenweise aufgebaut. Normale
Wertänderungen übertragen nur den betroffenen Bereich. Für schlecht komprimierbare
Bilder gibt es einen begrenzten, gepufferten Streifenmodus. Es gibt keinen
vollständigen Bildpuffer und keine Zusage für völlig unsichtbare SPI-Bildwechsel.

Im Designer **CPU und FPS anzeigen** aktivieren und **Speichern & übertragen**
drücken. Das lokale Overlay erscheint unten rechts (224 × 20 Pixel). Deaktivieren
und speichern blendet es wieder aus; die Einstellung bleibt in HA gespeichert.
Keine zusätzlichen HA-Bildupdates werden für das Overlay erzeugt.

- **CPU~**: statistische Näherung der mittleren Beschäftigung beider ESP32-Kerne,
  durch Abtasten der laufenden Tasks gegenüber den Idle-Tasks etwa 997-mal pro Sekunde.
- **FPS**: vollständig abgeschlossene HA-Bildupdates pro Sekunde, gemittelt über
  fünf Sekunden. Die Debug-Anzeige selbst und einzelne Teilbereiche zählen nicht.
  Bei unveränderten Daten sind 0 FPS korrekt; dies ist nicht die Scanfrequenz des TFT.

Die Messung wird ausgeschaltet, wenn das Overlay deaktiviert ist. Unter dem Overlay
liegende Buttons reagieren in dieser Ecke nicht auf Touch. Ältere Firmware kann
weiterhin Texte und HA-Werte anzeigen, unterstützt aber diese Verbesserungen nicht.

## Video / Livestream

### Größere Videos und Größenänderung ab 0.5.0

Mit Integration **0.5.0** und Firmware **0.5.0** lassen sich alle Elemente am Griff
unten rechts vergrößern/verkleinern. Position und Größe bleiben auf das Display
begrenzt. Die Zahlenfelder stehen ebenfalls weiterhin zur Verfügung.

Videofelder können bis **480 × 320 Pixel** groß sein. Der JPEG-Transport verwendet
den vorhandenen 64-KiB-Puffer des ESP32; kein Vollbildpuffer und kein PSRAM nötig.
Video wird unabhängig vom zehnsekündigen Heartbeat übertragen; alte Frames werden
verworfen. Buttons oberhalb des Videos bleiben Teil der Komposition, Touch-Ereignisse
bleiben bei unveränderter Aktionsrevision erhalten. JPEG ist verlustbehaftet;
bei sehr detailreichen Bildern wird die Qualität an den begrenzten Puffer angepasst.

Die **Zielbildrate** ist von 1 bis 20 FPS einstellbar, standardmäßig 15. Für den
ersten Versuch empfehlen wir **320 × 180 Pixel und 15 FPS**. Das schafft Spielraum
für das gewünschte Ziel von mindestens 10 gemessenen FPS. Es ist keine garantierte
Mindestbildrate: Größe, Quelle, WLAN und ESP32-Dekodierung bestimmen den realen Wert.
Bei einem Vollbild kann die Bildrate niedriger liegen. CPU/FPS-Overlay am Gerät
zur Messung verwenden. Im Designer bleibt die Vorschau auf etwa 1 FPS begrenzt.

Für größere Videos und die höhere Bildrate **Firmware 0.5.0 flashen**, dabei
`include/secrets.h` behalten. Anschließend HA/HACS aktualisieren, HA neu starten,
Designer neu laden und speichern. Vorhandene Touchkalibrierung bleibt erhalten.
Firmware 0.3.0 unterstützt weiterhin die bisherigen kleinen Streams mit 2 FPS.

### Erster Stream-MVP (0.4.x)

Firmware **0.3.0 reicht aus**. Nach dem HACS-Update Home Assistant vollständig
neu starten und den Designer neu laden. Ein Element hinzufügen und den Typ
**Video / Livestream** auswählen. Eine vorhandene HA-Kamera auswählen, mit
**HA-Medien auswählen** die Medienbibliothek öffnen oder eine direkte Video-URL
eintragen. Position und Größe festlegen und **Speichern & übertragen** drücken.

HA löst `camera.*` und `media-source://…` auf. Ein dauerhaft laufender FFmpeg-Prozess
dekodiert das Video außerhalb des HA-Eventloops. RTSP(S), HTTP(S) (z. B. HLS,
MJPEG, MP4) und RTMP(S) können verwendet werden, soweit die installierte FFmpeg-
Version die konkrete Quelle und deren Codec unterstützt. Kamera-Zugangsdaten
kommen aus der bestehenden HA-Integration; HA-Tokens werden nicht ans Display
übertragen. Ein Kamera-Substream verringert die Last auf dem HA-Host.

Der erste Stream-MVP unterstützt **ein Videofeld bis 160 × 120 Pixel**, **ohne Ton**,
mit **Ziel 2 FPS**. Jeder Video-Bildbereich passt vollständig in den Displaypuffer.
Die reale Bildrate hängt von Netzwerk, Quelle und HA-Host ab. Bei langsamer
Übertragung werden alte Frames verworfen; es wird keine wachsende Warteschlange
aufgebaut. Die Vorschau zeigt etwa einmal pro Sekunde den letzten dekodierten
Frame der gespeicherten Quelle. Buttons können oberhalb des Videos liegen;
Videobewegung verändert die Aktionszuordnung nicht.

Das ist ein laufender Videostream, kein wiederholter Kamera-Snapshot-Aufruf.
Bei Streamverlust erscheint **Stream offline**, danach erfolgt ein neuer Versuch
nach zehn Sekunden. Endliche Dateien starten nach dem Ende erneut. Entfernen
oder Ändern der Quelle sowie Entladen der Integration beendet den alten Decoder.

**Nicht abspielbar:** normale Webseiten, DRM-geschützte Inhalte, reine Audioquellen
und reine WebRTC-Kameras ohne abrufbare Videoquelle. Eine sichtbare Kamera in HA
allein garantiert deshalb noch keinen kompatiblen Stream. Größere Videoansichten
und höhere Bildraten benötigen einen weiteren Ausbau des Transports.

## Kommunikation und Support

### Streamdiagnose ab 0.4.1

Der Designer zeigt bei der ausgewählten gespeicherten Videoquelle den Status und
eine eingegrenzte Fehlermeldung, etwa fehlende Kamera-Stream-URL, Anmeldung
abgelehnt, Quelle nicht erreichbar, Timeout oder Decoder-/Formatfehler.
FFmpeg-Ausgaben werden nur begrenzt intern ausgewertet; URLs, Passwörter und Tokens
erscheinen nicht in diesen Meldungen oder Logs. RTSP verwendet den
protokollspezifischen TCP-Timeout statt der allgemeinen HTTP-Timeout-Option.

Die Integration nutzt die vorhandenen HA-Entitäten und kommuniziert lokal
mit dem Display auf Port 80. Der Geräteschlüssel wird in HA gespeichert.
Keine HA-Zugangsdaten werden auf das Display übertragen. Das Display ist
für das Heimnetz vorgesehen; Port 80 nicht ins Internet weiterleiten.

Fehler können unter [Issues](https://github.com/rbnstn/ha-desk-display-hacs/issues)
gemeldet werden. Bitte keine Passwörter, Geräteschlüssel oder HA-Tokens posten.

Dies ist das öffentliche Installationsrepository. Die Entwicklung und Tests
finden in einem separaten privaten Repository statt. Es werden nur ausgewählte
Integrationsdateien veröffentlicht, keine private Entwicklungshistorie.
