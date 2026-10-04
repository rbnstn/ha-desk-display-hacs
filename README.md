# Desk Display fÃ¼r Home Assistant

HACS-Integration fÃ¼r ein E32R35T-Display mit der Desk-Display-Firmware.
Version **0.9.0**, Home Assistant **2026.9 oder neuer**.

## Installation Ã¼ber HACS

1. **HACS â†’ Drei-Punkte-MenÃ¼ â†’ Benutzerdefinierte Repositories** Ã¶ffnen.
2. `https://github.com/rbnstn/ha-desk-display-hacs` eintragen und Typ
   **Integration** auswÃ¤hlen.
3. **Desk Display** suchen und **Herunterladen** wÃ¤hlen.
4. Home Assistant neu starten und die OberflÃ¤che mit **Strg + F5** neu laden.
5. Bei einer neuen Einrichtung: **Einstellungen â†’ GerÃ¤te & Dienste â†’
   Integration hinzufÃ¼gen â†’ Desk Display**. Display-IP und GerÃ¤teschlÃ¼ssel eingeben.

Bei einer vorhandenen manuellen Installation dieselben Schritte ausfÃ¼hren.
Die bestehende HA-Integration nicht lÃ¶schen: GerÃ¤teeinrichtung und gespeicherte
Layouts bleiben erhalten. Ein erneutes Flashen ist fÃ¼r diesen Wechsel nicht nÃ¶tig.
Weitere Updates werden Ã¼ber HACS heruntergeladen; anschlieÃŸend HA neu starten.

## Anzeige gestalten

Im Seitenleisten-Panel **Desk Display** lassen sich bis zu acht Texte oder
HA-Werte, Buttons oder Switches positionieren und SchriftgrÃ¶ÃŸe sowie Farben anpassen.
**Speichern & Ã¼bertragen** speichert das Layout und zeigt es auf dem Display.
Ã„nderungen ausgewÃ¤hlter HA-Werte aktualisieren Display und Vorschau automatisch.
Die Verbindung wird zusÃ¤tzlich alle zehn Sekunden geprÃ¼ft.

**Element entfernen** neben **Element hinzufÃ¼gen** lÃ¶scht das ausgewÃ¤hlte Element.
Die Ã„nderung mit **Speichern & Ã¼bertragen** dauerhaft Ã¼bernehmen.

Buttons unterstÃ¼tzen `button`, `input_button`, `script` und `lock` (Aktion `lock.open`); Switches unterstÃ¼tzen
`switch` und `input_boolean`. Aktionen werden nur durch Tippen am physischen Display
ausgelÃ¶st. Die Editor-Vorschau ist ausschlieÃŸlich zum Gestalten.

Der MVP unterstÃ¼tzt eine normale Seite pro Display und ein optionales Klingel-
Overlay. Pro Ansicht lÃ¤uft ein Videofeld.

## Optionales Klingel-Overlay ab 0.6.4

Im Designer **Klingel-Overlay (optional)** aufklappen, aktivieren und auswÃ¤hlen:

- **Klingel-AuslÃ¶ser**: `binary_sensor`, `event` oder `input_button`.
- **Overlay-Kamera**: eine vorhandene HA-Kamera.
- **TÃ¼rÃ¶ffner / Nuki-Schloss**: `button`, `input_button`, `script` oder `lock`.
  Schloss-EntitÃ¤ten verwenden `lock.open` zum Ã–ffnen der Falle. Das Schloss muss
  diese Funktion ohne PIN unterstÃ¼tzen; andernfalls ein passendes HA-Skript wÃ¤hlen.
- **Overlay-Kamera vorbereiten**: optional, standardmÃ¤ÃŸig aus. HA hÃ¤lt ein aktuelles
  Kamerabild bereit und verwendet beim Klingeln den bereits laufenden Decoder.
  ZusÃ¤tzliche Kamera-Verbindung und Rechenlast auf dem HA-Host; keine Standby-
  VideoÃ¼bertragung zum Display. Nach dem Speichern den ersten Kamerastart abwarten.
  Bis zu zwei Decoder (normales Videofeld und vorbereitete Overlay-Kamera).
  Ab 0.6.4 wird parallel ein HA-Kamerabild vorbereitet, solange der Decoder noch
  keinen aktuellen Streamframe liefert. Es wird hÃ¶chstens alle zwei Sekunden
  nach Abschluss des letzten Abrufs neu angefragt; bei laufendem Stream entfallen
  diese Abrufe. Das Overlay verwendet das vorbereitete Bild und wechselt danach
  zum Stream. Streamframes gelten 2,5 Sekunden, HA-Kamerabilder fÃ¼nf Sekunden als
  verwendbar. Die Anzeige **Kamera bereit** meldet Quelle und Empfangsalter.
  Sie bestÃ¤tigt den Empfang, nicht das Aufnahmealter eines von HA gecachten Bildes.
  Ohne verfÃ¼gbares Bild kann auch dieser Modus keine sofortige Ansicht garantieren.
  Beim Entladen oder Deaktivieren endet die Vorbereitung; veraltete Bereitschaftsbilder
  werden nicht als erstes Overlay-Bild verwendet.
- **Automatisch schlieÃŸen nach**: 5â€“300 Sekunden, standardmÃ¤ÃŸig 30.

Ab 0.6.4 zeigt der TÃ¼rknopf **Wird geÃ¶ffnet**, **Befehl ausgefÃ¼hrt**, **Fehler**
oder bei Timeout **Ergebnis unklar**. Die RÃ¼ckmeldung bestÃ¤tigt die Verarbeitung
in HA, nicht den physischen Durchgang. Optional einen **TÃ¼rkontakt** auswÃ¤hlen:
`binary_sensor` Ein = TÃ¼r offen, Aus = geschlossen. Fehlender/unverfÃ¼gbarer Kontakt
zeigt einen unbekannten Status. Ohne Kontakt wird bei Schloss-EntitÃ¤ten der
Schlosszustand angezeigt; â€žentriegeltâ€œ bedeutet nicht, dass die TÃ¼r offen steht.

**Nach TÃ¼raktion mindestens weiter anzeigen** stellt 5â€“300 Sekunden ein,
standardmÃ¤ÃŸig 45. Der Timer startet nach der Aktion erneut; eine bereits lÃ¤ngere
Restlaufzeit wird nicht verkÃ¼rzt. Wiederholtes Antippen innerhalb von drei Sekunden
und TÃ¼raktionen bei offenem Kontakt werden ignoriert. Unsichere oder fehlgeschlagene
Aktionen werden niemals automatisch wiederholt.

Mit **Speichern & Ã¼bertragen** Ã¼bernehmen. **Overlay-Vorschau** Ã¶ffnet nur die
Editor-Vorschau. **Overlay am Display testen** zeigt die gespeicherte Ansicht am
GerÃ¤t und lÃ¶st keine TÃ¼raktion aus. Die TÃ¼r wird ausschlieÃŸlich durch Antippen
des TÃ¼rÃ¶ffner-Buttons am Display betÃ¤tigt. Fehlende/unverfÃ¼gbare Aktionen bleiben
inaktiv. Bei aktivem Overlay werden Hintergrund-Buttons nicht bedient.

Ein Binary-Sensor lÃ¶st bei Aus â†’ Ein aus. Ereignis-/Input-Button-EntitÃ¤ten lÃ¶sen
bei einem neuen aktuellen Zeitstempel aus; alte wiederhergestellte Zeitstempel
und das bloÃŸe Initialisieren einer EntitÃ¤t zeigen kein Overlay. WÃ¤hle die
Klingel-/Besucher-EntitÃ¤t und nicht den Bewegungsmelder. Wiederholtes Klingeln
startet die RÃ¼ckkehrzeit neu. Nach Ablauf wird das normale Layout wieder angezeigt.

Die erste Overlay-Vorlage hat feste Positionen: Ãœberschrift, Kamera (432 Ã— 180)
und TÃ¼rÃ¶ffner. Die normale Anzeige bleibt frei gestaltbar inklusive GrÃ¶ÃŸenÃ¤nderung.
Ein vorhandener Hintergrund-Stream pausiert wÃ¤hrend des Overlays; sein letztes
Bild bleibt als Hintergrund, danach startet er neu. Ohne Kameravorbereitung oder
bei fehlendem aktuellem Frame kann zunÃ¤chst der Offline-Platzhalter sichtbar sein.
Die Vorbereitung verkÃ¼rzt den erneuten Kamerastart; eine konkrete Latenz hÃ¤ngt
von Kamera, HA-Host und Netzwerk ab. Die Kamera bleibt bei
hÃ¶chstens 1 FPS; das Overlay wird bei einem HA-Neustart nicht wiederhergestellt.
FÃ¼r dieses Feature mit vorhandener JPEG-Firmware ist kein erneutes Flashen nÃ¶tig.

## Display-Firmware

Das Display braucht die passende Desk-Display-Firmware und muss Ã¼ber WLAN
von HA erreichbar sein. Dieses Repository verteilt ausschlieÃŸlich die
HA-Integration; Firmware und deren Entwicklung werden separat verwaltet.
Die Hersteller-Demo ist nicht kompatibel. HACS flasht keine ESP32-Firmware.

**Touch benÃ¶tigt Firmware 0.2.0.** Nach dem Flashen die angezeigten Eckmarkierungen
antippen. Die Kalibrierung wird gespeichert. FÃ¼r eine erneute Kalibrierung BOOT
am bereits laufenden Display drei Sekunden gedrÃ¼ckt halten, dann loslassen.
Ã„ltere Firmware unterstÃ¼tzt weiterhin Texte und HA-Werte.

HA holt Touch-Ereignisse etwa einmal pro Sekunde ab. Jeder Druck lÃ¶st hÃ¶chstens
eine Aktion aus; lange gehaltene BerÃ¼hrungen werden nicht wiederholt. Veraltete
Ereignisse, andere Layoutversionen und nicht verfÃ¼gbare EntitÃ¤ten werden verworfen.
Eine wegen Verbindungsverlust oder ZeitÃ¼berschreitung unsichere Aktion wird nicht
automatisch wiederholt. Der Switch-Zustand kommt immer aus HA.

## Ruhigere Bildupdates und Debug-Anzeige (Firmware 0.3.0)

Neue Firmware empfÃ¤ngt ein komprimiertes Bild bzw. den geÃ¤nderten Bildbereich
vollstÃ¤ndig, bevor sie ihn Ã¼ber SPI zeichnet. Dadurch wird der Bildschirm nicht
mehr wÃ¤hrend des langsamen WLAN-Empfangs zeilenweise aufgebaut. Normale
WertÃ¤nderungen Ã¼bertragen nur den betroffenen Bereich. FÃ¼r schlecht komprimierbare
Bilder gibt es einen begrenzten, gepufferten Streifenmodus. Es gibt keinen
vollstÃ¤ndigen Bildpuffer und keine Zusage fÃ¼r vÃ¶llig unsichtbare SPI-Bildwechsel.

Im Designer **CPU und FPS anzeigen** aktivieren und **Speichern & Ã¼bertragen**
drÃ¼cken. Das lokale Overlay erscheint unten rechts (224 Ã— 20 Pixel). Deaktivieren
und speichern blendet es wieder aus; die Einstellung bleibt in HA gespeichert.
Keine zusÃ¤tzlichen HA-Bildupdates werden fÃ¼r das Overlay erzeugt.

- **CPU~**: statistische NÃ¤herung der mittleren BeschÃ¤ftigung beider ESP32-Kerne,
  durch Abtasten der laufenden Tasks gegenÃ¼ber den Idle-Tasks etwa 997-mal pro Sekunde.
- **FPS**: vollstÃ¤ndig abgeschlossene HA-Bildupdates pro Sekunde, gemittelt Ã¼ber
  fÃ¼nf Sekunden. Die Debug-Anzeige selbst und einzelne Teilbereiche zÃ¤hlen nicht.
  Bei unverÃ¤nderten Daten sind 0 FPS korrekt; dies ist nicht die Scanfrequenz des TFT.

Die Messung wird ausgeschaltet, wenn das Overlay deaktiviert ist. Unter dem Overlay
liegende Buttons reagieren in dieser Ecke nicht auf Touch. Ã„ltere Firmware kann
weiterhin Texte und HA-Werte anzeigen, unterstÃ¼tzt aber diese Verbesserungen nicht.

## Video / Livestream

### GrÃ¶ÃŸere Videos und GrÃ¶ÃŸenÃ¤nderung ab 0.5.0

Mit Integration **0.5.0** und Firmware **0.5.0** lassen sich alle Elemente am Griff
unten rechts vergrÃ¶ÃŸern/verkleinern. Position und GrÃ¶ÃŸe bleiben auf das Display
begrenzt. Die Zahlenfelder stehen ebenfalls weiterhin zur VerfÃ¼gung.

Videofelder kÃ¶nnen bis **480 Ã— 320 Pixel** groÃŸ sein. Der JPEG-Transport verwendet
den vorhandenen 64-KiB-Puffer des ESP32; kein Vollbildpuffer und kein PSRAM nÃ¶tig.
Video wird unabhÃ¤ngig vom zehnsekÃ¼ndigen Heartbeat Ã¼bertragen; alte Frames werden
verworfen. Buttons oberhalb des Videos bleiben Teil der Komposition, Touch-Ereignisse
bleiben bei unverÃ¤nderter Aktionsrevision erhalten. JPEG ist verlustbehaftet;
bei sehr detailreichen Bildern wird die QualitÃ¤t an den begrenzten Puffer angepasst.

Ab Integration **0.5.1** sind Streams fest auf **hÃ¶chstens 1 FPS** begrenzt, auch
bei Ã¤lteren gespeicherten Layouts mit hÃ¶herer Zielbildrate. HA-Werte und Touch-
Aktionen werden unabhÃ¤ngig vom Videotakt verarbeitet. Es werden weiterhin die
neuesten verfÃ¼gbaren Bilder verwendet und alte Frames verworfen. Bei langsamer
Quelle oder Verbindung kann die Bildrate niedriger sein. Der FPS-ZÃ¤hler zÃ¤hlt
auch andere BildÃ¤nderungen; solche Updates kÃ¶nnen ihn Ã¼ber 1 steigen lassen.

FÃ¼r grÃ¶ÃŸere Videos **Firmware 0.5.0 oder neuer flashen**, dabei
`include/secrets.h` behalten. AnschlieÃŸend HA/HACS aktualisieren, HA neu starten,
Designer neu laden und speichern. Vorhandene Touchkalibrierung bleibt erhalten.
FÃ¼r die Begrenzung auf 1 FPS genÃ¼gt das HACS-Update; Firmware 0.3.0 unterstÃ¼tzt
weiterhin kleine Streams bis 160 Ã— 120 Pixel, ebenfalls mit hÃ¶chstens 1 FPS.

### Erster Stream-MVP (0.4.x)

Firmware **0.3.0 reicht aus**. Nach dem HACS-Update Home Assistant vollstÃ¤ndig
neu starten und den Designer neu laden. Ein Element hinzufÃ¼gen und den Typ
**Video / Livestream** auswÃ¤hlen. Eine vorhandene HA-Kamera auswÃ¤hlen, mit
**HA-Medien auswÃ¤hlen** die Medienbibliothek Ã¶ffnen oder eine direkte Video-URL
eintragen. Position und GrÃ¶ÃŸe festlegen und **Speichern & Ã¼bertragen** drÃ¼cken.

HA lÃ¶st `camera.*` und `media-source://â€¦` auf. Ein dauerhaft laufender FFmpeg-Prozess
dekodiert das Video auÃŸerhalb des HA-Eventloops. RTSP(S), HTTP(S) (z. B. HLS,
MJPEG, MP4) und RTMP(S) kÃ¶nnen verwendet werden, soweit die installierte FFmpeg-
Version die konkrete Quelle und deren Codec unterstÃ¼tzt. Kamera-Zugangsdaten
kommen aus der bestehenden HA-Integration; HA-Tokens werden nicht ans Display
Ã¼bertragen. Ein Kamera-Substream verringert die Last auf dem HA-Host.

Der erste Stream-MVP unterstÃ¼tzt **ein Videofeld bis 160 Ã— 120 Pixel**, **ohne Ton**,
mit **Ziel 2 FPS**. Jeder Video-Bildbereich passt vollstÃ¤ndig in den Displaypuffer.
Die reale Bildrate hÃ¤ngt von Netzwerk, Quelle und HA-Host ab. Bei langsamer
Ãœbertragung werden alte Frames verworfen; es wird keine wachsende Warteschlange
aufgebaut. Die Vorschau zeigt etwa einmal pro Sekunde den letzten dekodierten
Frame der gespeicherten Quelle. Buttons kÃ¶nnen oberhalb des Videos liegen;
Videobewegung verÃ¤ndert die Aktionszuordnung nicht.

Das ist ein laufender Videostream, kein wiederholter Kamera-Snapshot-Aufruf.
Bei Streamverlust erscheint **Stream offline**, danach erfolgt ein neuer Versuch
nach zehn Sekunden. Endliche Dateien starten nach dem Ende erneut. Entfernen
oder Ã„ndern der Quelle sowie Entladen der Integration beendet den alten Decoder.

**Nicht abspielbar:** normale Webseiten, DRM-geschÃ¼tzte Inhalte, reine Audioquellen
und reine WebRTC-Kameras ohne abrufbare Videoquelle. Eine sichtbare Kamera in HA
allein garantiert deshalb noch keinen kompatiblen Stream. GrÃ¶ÃŸere Videoansichten
und hÃ¶here Bildraten benÃ¶tigen einen weiteren Ausbau des Transports.

## Kommunikation und Support

### Streamdiagnose ab 0.4.1

Der Designer zeigt bei der ausgewÃ¤hlten gespeicherten Videoquelle den Status und
eine eingegrenzte Fehlermeldung, etwa fehlende Kamera-Stream-URL, Anmeldung
abgelehnt, Quelle nicht erreichbar, Timeout oder Decoder-/Formatfehler.
FFmpeg-Ausgaben werden nur begrenzt intern ausgewertet; URLs, PasswÃ¶rter und Tokens
erscheinen nicht in diesen Meldungen oder Logs. RTSP verwendet den
protokollspezifischen TCP-Timeout statt der allgemeinen HTTP-Timeout-Option.

Die Integration nutzt die vorhandenen HA-EntitÃ¤ten und kommuniziert lokal
mit dem Display auf Port 80. Der GerÃ¤teschlÃ¼ssel wird in HA gespeichert.
Keine HA-Zugangsdaten werden auf das Display Ã¼bertragen. Das Display ist
fÃ¼r das Heimnetz vorgesehen; Port 80 nicht ins Internet weiterleiten.

Fehler kÃ¶nnen unter [Issues](https://github.com/rbnstn/ha-desk-display-hacs/issues)
gemeldet werden. Bitte keine PasswÃ¶rter, GerÃ¤teschlÃ¼ssel oder HA-Tokens posten.

Dies ist das Ã¶ffentliche Installationsrepository. Die Entwicklung und Tests
finden in einem separaten privaten Repository statt. Es werden nur ausgewÃ¤hlte
Integrationsdateien verÃ¶ffentlicht, keine private Entwicklungshistorie.

## Material-Design ab 0.7.0

Im Designer unter **Display-Design** zwischen Klassisch, Material Â· Dunkel und
Material Â· Hell wÃ¤hlen. Speichern & Ã¼bertragen Ã¼bernimmt das Design. Positionen,
GrÃ¶ÃŸen und EntitÃ¤ten bleiben erhalten; Hintergrund und Textfarben werden beim
Designwechsel gesetzt. Bestehende Layouts bleiben zunÃ¤chst klassisch.

Material bietet Karten fÃ¼r HA-Werte, zentrierte Buttons, Schiebeschalter und
abgerundete Videofelder. Pro Element lassen sich KartenflÃ¤che, Kartenfarbe,
Eckenradius und Textausrichtung anpassen. Ab 62 Pixel HÃ¶he erscheinen Sensorlabel
und Wert auf getrennten Zeilen. Das optionale Klingel-Overlay folgt dem Design.
Die Darstellung entsteht in HA; die Firmware und das Limit von 1 FPS bleiben
unverÃ¤ndert. Nach dem HACS-Update HA neu starten und den Designer neu laden
(gegebenenfalls Strg+F5). Kein Firmware-Update erforderlich.

## Layout-Werkzeuge ab 0.7.1

Unter **Anordnen** das ausgewÃ¤hlte Element duplizieren, eine Ebene nach vorn oder
zurÃ¼ck verschieben und am gesamten Display ausrichten. Duplikate Ã¼bernehmen
EntitÃ¤t, Stil und GrÃ¶ÃŸe und werden innerhalb des Displays leicht versetzt.
Die oberste Ebene bestimmt auch das Touch-Ziel. Videofelder lassen sich nicht
duplizieren, da weiterhin eine Videoquelle pro Ansicht unterstÃ¼tzt wird.
AnschlieÃŸend **Speichern & Ã¼bertragen**. Kein Firmware-Update erforderlich.

## Werte, Uhrzeit und Bilder ab 0.8.0

HA-Werte zeigen die Beschriftung links und den Wert rechts. Bei hohen Karten
stehen beide auf getrennten Zeilen. Im Designer sind Umrechnungsfaktor, eigene
Einheit, Nachkommastellen und Vorzeichenwechsel einstellbar. Beispiel: Faktor
0,001 + Einheit kW rechnet 2500 W in 2,5 kW um. Vorzeichenwechsel multipliziert
zusÃ¤tzlich mit -1. Eine leere eigene Einheit blendet die Einheit aus; der Button
**HA-Einheit verwenden** stellt die ursprÃ¼ngliche Einheit wieder her. Diese
Ã„nderungen betreffen nur die Anzeige, nicht die HA-EntitÃ¤t.

Eine optionale Ersatz-EntitÃ¤t Ã¼bernimmt die Anzeige bei 0, fehlendem Wert oder
beidem. GeprÃ¼ft wird der ursprÃ¼ngliche HA-Wert vor der Umrechnung; fehlend sind
unbekannt, nicht verfÃ¼gbar, null oder leer. Auch Ã„nderungen des Ersatzwerts lÃ¶sen
eine Aktualisierung aus. Ist der Ersatz ebenfalls nicht verfÃ¼gbar, erscheint
Nicht verfÃ¼gbar. Umrechnung und eigene Einheit gelten auch fÃ¼r den Ersatz.

Neue Elementtypen **Uhrzeit / Datum** und **Bild / Logo** lassen sich frei
positionieren und vergrÃ¶ÃŸern. Die Uhr verwendet die HA-Zeitzone und zeigt Minuten;
sie aktualisiert sich spÃ¤testens etwa zehn Sekunden nach dem Minutenwechsel.
Bilder als PNG, JPEG oder WebP hochladen (maximal 5 MB Eingabe); der Designer
verkleinert sie auf maximal 480 Ã— 320 und 100 KB. Transparente PNG-Logos werden
unterstÃ¼tzt. VollstÃ¤ndige Anzeige oder zugeschnittenes FÃ¼llen ist wÃ¤hlbar. Bilder
werden im Layout gespeichert; externe Bild-URLs und SVG sind nicht unterstÃ¼tzt.
Nach dem HACS-Update HA neu starten und den Designer mit Strg+F5 neu laden.
Kein Firmware-Update erforderlich.

## Kompakter Designer ab 0.9.0

Vorschau und Speichern bleiben im sichtbaren Arbeitsbereich. Rechts scrollen
nur die Einstellungen. Die Reiter **Element**, **Display** und **Klingel** trennen
Elementdaten von allgemeinen Einstellungen und dem optionalen Overlay.
Anordnen, Umrechnung & Ersatzwert, Position & GrÃ¶ÃŸe und Aussehen sind aufklappbar.
GeÃ¶ffnete Gruppen bleiben wÃ¤hrend der Bearbeitung erhalten.

Die Elementleiste unter der Vorschau ermÃ¶glicht einen schnellen Wechsel;
Umbenennungen erscheinen sofort in Leiste und Auswahl. Das markierte Element
lÃ¤sst sich nach Fokussieren des Vorschaufelds mit Pfeiltasten um 1 Pixel bewegen,
mit Shift um 10 Pixel. Ziehen und der grÃ¼ne Griff fÃ¼r GrÃ¶ÃŸenÃ¤nderung bleiben.
Eine Anzeige neben dem Speichern-Button zeigt ungespeicherte Ã„nderungen.
Auch Ã„nderungen wÃ¤hrend eines laufenden Speichervorgangs bleiben als
ungespeichert erkennbar; eine Ã¤ltere Speichervorschau Ã¼berschreibt sie nicht.
Der Designer passt Vorschau und Seitenleiste auch an schmale Fenster an.
Nach dem HACS-Update HA neu starten und den Designer mit Strg+F5 neu laden.
Kein Firmware-Update erforderlich.

## Version 0.10.0: Designer editing tools

Rückgängig/Wiederholen mit 40 Schritten, optionales Raster mit Kantenfang, Mehrfachauswahl per Strg/Klick, Gruppieren, gemeinsam verschieben, ausrichten und verteilen. Gruppen werden im Layout gespeichert. Kein Firmware-Update nötig.
