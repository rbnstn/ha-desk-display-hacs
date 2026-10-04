# Desk Display für Home Assistant

HACS-Integration für ein E32R35T-Display mit der Desk-Display-Firmware.
Version **0.9.0**, Home Assistant **2026.9 oder neuer**.

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

Buttons unterstützen `button`, `input_button`, `script` und `lock` (Aktion `lock.open`); Switches unterstützen
`switch` und `input_boolean`. Aktionen werden nur durch Tippen am physischen Display
ausgelöst. Die Editor-Vorschau ist ausschließlich zum Gestalten.

Der MVP unterstützt eine normale Seite pro Display und ein optionales Klingel-
Overlay. Pro Ansicht läuft ein Videofeld.

## Optionales Klingel-Overlay ab 0.6.4

Im Designer **Klingel-Overlay (optional)** aufklappen, aktivieren und auswählen:

- **Klingel-Auslöser**: `binary_sensor`, `event` oder `input_button`.
- **Overlay-Kamera**: eine vorhandene HA-Kamera.
- **Türöffner / Nuki-Schloss**: `button`, `input_button`, `script` oder `lock`.
  Schloss-Entitäten verwenden `lock.open` zum Öffnen der Falle. Das Schloss muss
  diese Funktion ohne PIN unterstützen; andernfalls ein passendes HA-Skript wählen.
- **Overlay-Kamera vorbereiten**: optional, standardmäßig aus. HA hält ein aktuelles
  Kamerabild bereit und verwendet beim Klingeln den bereits laufenden Decoder.
  Zusätzliche Kamera-Verbindung und Rechenlast auf dem HA-Host; keine Standby-
  Videoübertragung zum Display. Nach dem Speichern den ersten Kamerastart abwarten.
  Bis zu zwei Decoder (normales Videofeld und vorbereitete Overlay-Kamera).
  Ab 0.6.4 wird parallel ein HA-Kamerabild vorbereitet, solange der Decoder noch
  keinen aktuellen Streamframe liefert. Es wird höchstens alle zwei Sekunden
  nach Abschluss des letzten Abrufs neu angefragt; bei laufendem Stream entfallen
  diese Abrufe. Das Overlay verwendet das vorbereitete Bild und wechselt danach
  zum Stream. Streamframes gelten 2,5 Sekunden, HA-Kamerabilder fünf Sekunden als
  verwendbar. Die Anzeige **Kamera bereit** meldet Quelle und Empfangsalter.
  Sie bestätigt den Empfang, nicht das Aufnahmealter eines von HA gecachten Bildes.
  Ohne verfügbares Bild kann auch dieser Modus keine sofortige Ansicht garantieren.
  Beim Entladen oder Deaktivieren endet die Vorbereitung; veraltete Bereitschaftsbilder
  werden nicht als erstes Overlay-Bild verwendet.
- **Automatisch schließen nach**: 5–300 Sekunden, standardmäßig 30.

Ab 0.6.4 zeigt der Türknopf **Wird geöffnet**, **Befehl ausgeführt**, **Fehler**
oder bei Timeout **Ergebnis unklar**. Die Rückmeldung bestätigt die Verarbeitung
in HA, nicht den physischen Durchgang. Optional einen **Türkontakt** auswählen:
`binary_sensor` Ein = Tür offen, Aus = geschlossen. Fehlender/unverfügbarer Kontakt
zeigt einen unbekannten Status. Ohne Kontakt wird bei Schloss-Entitäten der
Schlosszustand angezeigt; „entriegelt“ bedeutet nicht, dass die Tür offen steht.

**Nach Türaktion mindestens weiter anzeigen** stellt 5–300 Sekunden ein,
standardmäßig 45. Der Timer startet nach der Aktion erneut; eine bereits längere
Restlaufzeit wird nicht verkürzt. Wiederholtes Antippen innerhalb von drei Sekunden
und Türaktionen bei offenem Kontakt werden ignoriert. Unsichere oder fehlgeschlagene
Aktionen werden niemals automatisch wiederholt.

Mit **Speichern & übertragen** übernehmen. **Overlay-Vorschau** öffnet nur die
Editor-Vorschau. **Overlay am Display testen** zeigt die gespeicherte Ansicht am
Gerät und löst keine Türaktion aus. Die Tür wird ausschließlich durch Antippen
des Türöffner-Buttons am Display betätigt. Fehlende/unverfügbare Aktionen bleiben
inaktiv. Bei aktivem Overlay werden Hintergrund-Buttons nicht bedient.

Ein Binary-Sensor löst bei Aus → Ein aus. Ereignis-/Input-Button-Entitäten lösen
bei einem neuen aktuellen Zeitstempel aus; alte wiederhergestellte Zeitstempel
und das bloße Initialisieren einer Entität zeigen kein Overlay. Wähle die
Klingel-/Besucher-Entität und nicht den Bewegungsmelder. Wiederholtes Klingeln
startet die Rückkehrzeit neu. Nach Ablauf wird das normale Layout wieder angezeigt.

Die erste Overlay-Vorlage hat feste Positionen: Überschrift, Kamera (432 × 180)
und Türöffner. Die normale Anzeige bleibt frei gestaltbar inklusive Größenänderung.
Ein vorhandener Hintergrund-Stream pausiert während des Overlays; sein letztes
Bild bleibt als Hintergrund, danach startet er neu. Ohne Kameravorbereitung oder
bei fehlendem aktuellem Frame kann zunächst der Offline-Platzhalter sichtbar sein.
Die Vorbereitung verkürzt den erneuten Kamerastart; eine konkrete Latenz hängt
von Kamera, HA-Host und Netzwerk ab. Die Kamera bleibt bei
höchstens 1 FPS; das Overlay wird bei einem HA-Neustart nicht wiederhergestellt.
Für dieses Feature mit vorhandener JPEG-Firmware ist kein erneutes Flashen nötig.

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

Ab Integration **0.5.1** sind Streams fest auf **höchstens 1 FPS** begrenzt, auch
bei älteren gespeicherten Layouts mit höherer Zielbildrate. HA-Werte und Touch-
Aktionen werden unabhängig vom Videotakt verarbeitet. Es werden weiterhin die
neuesten verfügbaren Bilder verwendet und alte Frames verworfen. Bei langsamer
Quelle oder Verbindung kann die Bildrate niedriger sein. Der FPS-Zähler zählt
auch andere Bildänderungen; solche Updates können ihn über 1 steigen lassen.

Für größere Videos **Firmware 0.5.0 oder neuer flashen**, dabei
`include/secrets.h` behalten. Anschließend HA/HACS aktualisieren, HA neu starten,
Designer neu laden und speichern. Vorhandene Touchkalibrierung bleibt erhalten.
Für die Begrenzung auf 1 FPS genügt das HACS-Update; Firmware 0.3.0 unterstützt
weiterhin kleine Streams bis 160 × 120 Pixel, ebenfalls mit höchstens 1 FPS.

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

## Material-Design ab 0.7.0

Im Designer unter **Display-Design** zwischen Klassisch, Material · Dunkel und
Material · Hell wählen. Speichern & übertragen übernimmt das Design. Positionen,
Größen und Entitäten bleiben erhalten; Hintergrund und Textfarben werden beim
Designwechsel gesetzt. Bestehende Layouts bleiben zunächst klassisch.

Material bietet Karten für HA-Werte, zentrierte Buttons, Schiebeschalter und
abgerundete Videofelder. Pro Element lassen sich Kartenfläche, Kartenfarbe,
Eckenradius und Textausrichtung anpassen. Ab 62 Pixel Höhe erscheinen Sensorlabel
und Wert auf getrennten Zeilen. Das optionale Klingel-Overlay folgt dem Design.
Die Darstellung entsteht in HA; die Firmware und das Limit von 1 FPS bleiben
unverändert. Nach dem HACS-Update HA neu starten und den Designer neu laden
(gegebenenfalls Strg+F5). Kein Firmware-Update erforderlich.

## Layout-Werkzeuge ab 0.7.1

Unter **Anordnen** das ausgewählte Element duplizieren, eine Ebene nach vorn oder
zurück verschieben und am gesamten Display ausrichten. Duplikate übernehmen
Entität, Stil und Größe und werden innerhalb des Displays leicht versetzt.
Die oberste Ebene bestimmt auch das Touch-Ziel. Videofelder lassen sich nicht
duplizieren, da weiterhin eine Videoquelle pro Ansicht unterstützt wird.
Anschließend **Speichern & übertragen**. Kein Firmware-Update erforderlich.

## Werte, Uhrzeit und Bilder ab 0.8.0

HA-Werte zeigen die Beschriftung links und den Wert rechts. Bei hohen Karten
stehen beide auf getrennten Zeilen. Im Designer sind Umrechnungsfaktor, eigene
Einheit, Nachkommastellen und Vorzeichenwechsel einstellbar. Beispiel: Faktor
0,001 + Einheit kW rechnet 2500 W in 2,5 kW um. Vorzeichenwechsel multipliziert
zusätzlich mit -1. Eine leere eigene Einheit blendet die Einheit aus; der Button
**HA-Einheit verwenden** stellt die ursprüngliche Einheit wieder her. Diese
Änderungen betreffen nur die Anzeige, nicht die HA-Entität.

Eine optionale Ersatz-Entität übernimmt die Anzeige bei 0, fehlendem Wert oder
beidem. Geprüft wird der ursprüngliche HA-Wert vor der Umrechnung; fehlend sind
unbekannt, nicht verfügbar, null oder leer. Auch Änderungen des Ersatzwerts lösen
eine Aktualisierung aus. Ist der Ersatz ebenfalls nicht verfügbar, erscheint
Nicht verfügbar. Umrechnung und eigene Einheit gelten auch für den Ersatz.

Neue Elementtypen **Uhrzeit / Datum** und **Bild / Logo** lassen sich frei
positionieren und vergrößern. Die Uhr verwendet die HA-Zeitzone und zeigt Minuten;
sie aktualisiert sich spätestens etwa zehn Sekunden nach dem Minutenwechsel.
Bilder als PNG, JPEG oder WebP hochladen (maximal 5 MB Eingabe); der Designer
verkleinert sie auf maximal 480 × 320 und 100 KB. Transparente PNG-Logos werden
unterstützt. Vollständige Anzeige oder zugeschnittenes Füllen ist wählbar. Bilder
werden im Layout gespeichert; externe Bild-URLs und SVG sind nicht unterstützt.
Nach dem HACS-Update HA neu starten und den Designer mit Strg+F5 neu laden.
Kein Firmware-Update erforderlich.

## Kompakter Designer ab 0.9.0

Vorschau und Speichern bleiben im sichtbaren Arbeitsbereich. Rechts scrollen
nur die Einstellungen. Die Reiter **Element**, **Display** und **Klingel** trennen
Elementdaten von allgemeinen Einstellungen und dem optionalen Overlay.
Anordnen, Umrechnung & Ersatzwert, Position & Größe und Aussehen sind aufklappbar.
Geöffnete Gruppen bleiben während der Bearbeitung erhalten.

Die Elementleiste unter der Vorschau ermöglicht einen schnellen Wechsel;
Umbenennungen erscheinen sofort in Leiste und Auswahl. Das markierte Element
lässt sich nach Fokussieren des Vorschaufelds mit Pfeiltasten um 1 Pixel bewegen,
mit Shift um 10 Pixel. Ziehen und der grüne Griff für Größenänderung bleiben.
Eine Anzeige neben dem Speichern-Button zeigt ungespeicherte Änderungen.
Auch Änderungen während eines laufenden Speichervorgangs bleiben als
ungespeichert erkennbar; eine ältere Speichervorschau überschreibt sie nicht.
Der Designer passt Vorschau und Seitenleiste auch an schmale Fenster an.
Nach dem HACS-Update HA neu starten und den Designer mit Strg+F5 neu laden.
Kein Firmware-Update erforderlich.

## Version 0.10.0: Designer editing tools

Rückgängig/Wiederholen mit 40 Schritten, optionales Raster mit Kantenfang, Mehrfachauswahl per Strg/Klick, Gruppieren, gemeinsam verschieben, ausrichten und verteilen. Gruppen werden im Layout gespeichert. Kein Firmware-Update nötig.

## Version 0.11.0: State rules

Bedingte Textfarben und Symbol-Präfixe (bis vier Regeln), Sichtbarkeit nach HA-Zustand. Versteckte Elemente haben keine Touch-Aktion. Regeln reagieren auch auf zusätzliche Entitäten und verwenden Rohwerte. Kein Firmware-Update nötig.

## Version 0.12.0: Safe preview and layout recovery

Vorschau-Simulation für HA-Zustände und Tür-Rückmeldungen ohne Geräteaktion. Layout- und Komponenten-Dateien exportieren/importieren, serverseitig prüfen; drei automatische Sicherungen der vorherigen gespeicherten Layouts. Wiederherstellen bleibt bis zum Speichern ein Entwurf. Kein Firmware-Update nötig.

## Version 0.13.0: Pages and reusable templates

Bis vier Seiten mit Touch-Navigation, optionalem Wechsel (15–300 Sekunden) und Pause während des Klingel-Overlays. Vorlagen für Werte, Schalter, Uhr/Datum und Kamera; eigene Gruppen per Komponenten-Datei wiederverwenden. Die unteren 44 Pixel bleiben bei mehreren Seiten für Navigation und Status frei. Ein Stream pro aktiver Seite, weiterhin maximal 1 FPS. Kein Firmware-Update nötig.

## Version 0.14.0: Device controls and firmware updates

Helligkeit, Nachtzeitplan und HA-Lichtentität, Aufhellen beim Klingeln, Verbindungsalter und Zeitstempel-Sensor. Authentifizierter Firmware-Upload mit Datei- und Geräteprüfung im Designer. Firmware 0.6.0 einmalig per USB für Helligkeit, Offline-Markierung mit letztem Bild und spätere Updates über WLAN. Alle Designer-Funktionen bleiben mit älterer Firmware nutzbar. Hardwarefunktionen sind implementiert und werden kompiliert, der reale Gerätetest steht noch aus.

## Version 0.14.1: Gerätefunktionen und geprüfte Verbindung

Enthält die Gerätefunktionen aus 0.14.0 sowie bestätigte Daten-Heartbeats, geprüfte Firmware-Uploads, globale Debug-Einstellungen und eine größere Smartphone-Vorschau. HA-Vertragsprüfungen, Firmware-Build und Designer-Tests erfolgreich. Neue Hardwarefunktionen benötigen Firmware 0.6.0; einmalig per USB installieren.

## Version 0.14.2: Einfacher anordnen und getrennt skalieren

Ausrichtungs- und Verteilbuttons sowie das Ausrichtungs-Dropdown entfernt; Raster und Hilfslinien bleiben. Gruppen haben einen gemeinsamen gelben Rahmen und nummerierte Kennzeichnungen in Elementliste und Auswahl. Zusätzliche Griffe ändern nur Breite oder Höhe; der Eckgriff ändert beide. Keine Firmware-Aktualisierung erforderlich. Achsentreues Ziehen, Grenzen und Rückgängig im Browser und Node geprüft.

## Version 0.14.3: Verständliche Farbregeln

Farben & Sichtbarkeit ist ein eigener Abschnitt neben Inhalt & Daten. Regeln sind offene Wenn-dann-Karten mit verständlicher Zusammenfassung statt mehrfach verschachtelter Menüs. Der eigene Elementwert kann ohne zusätzliche Entitätsauswahl verwendet werden; andere Entitäten bleiben auswählbar. Nicht verfügbar blendet das Vergleichsfeld aus. Bestehende Regeln bleiben erhalten. Keine Firmware-Aktualisierung erforderlich.

## Version 0.14.4: Elemente direkt und gezielt hinzufügen

Element hinzufügen öffnet sofort eine Auswahl mit sieben verständlich beschriebenen Elementarten. Die Wahl legt das passende Element mit typgerechter Größe an, sucht möglichst freien Platz und öffnet automatisch Inhalt & Daten. Nur das neue Element wird ausgewählt. Elementtyp bleibt oben direkt erreichbar. Abbrechen verändert den Entwurf nicht; ein zweites Videofeld ist gesperrt. Keine Firmware-Aktualisierung erforderlich.
