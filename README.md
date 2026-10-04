# Desk Display fÃƒÂ¼r Home Assistant

HACS-Integration fÃƒÂ¼r ein E32R35T-Display mit der Desk-Display-Firmware.
Version **0.9.0**, Home Assistant **2026.9 oder neuer**.

## Installation ÃƒÂ¼ber HACS

1. **HACS Ã¢â€ â€™ Drei-Punkte-MenÃƒÂ¼ Ã¢â€ â€™ Benutzerdefinierte Repositories** ÃƒÂ¶ffnen.
2. `https://github.com/rbnstn/ha-desk-display-hacs` eintragen und Typ
   **Integration** auswÃƒÂ¤hlen.
3. **Desk Display** suchen und **Herunterladen** wÃƒÂ¤hlen.
4. Home Assistant neu starten und die OberflÃƒÂ¤che mit **Strg + F5** neu laden.
5. Bei einer neuen Einrichtung: **Einstellungen Ã¢â€ â€™ GerÃƒÂ¤te & Dienste Ã¢â€ â€™
   Integration hinzufÃƒÂ¼gen Ã¢â€ â€™ Desk Display**. Display-IP und GerÃƒÂ¤teschlÃƒÂ¼ssel eingeben.

Bei einer vorhandenen manuellen Installation dieselben Schritte ausfÃƒÂ¼hren.
Die bestehende HA-Integration nicht lÃƒÂ¶schen: GerÃƒÂ¤teeinrichtung und gespeicherte
Layouts bleiben erhalten. Ein erneutes Flashen ist fÃƒÂ¼r diesen Wechsel nicht nÃƒÂ¶tig.
Weitere Updates werden ÃƒÂ¼ber HACS heruntergeladen; anschlieÃƒÅ¸end HA neu starten.

## Anzeige gestalten

Im Seitenleisten-Panel **Desk Display** lassen sich bis zu acht Texte oder
HA-Werte, Buttons oder Switches positionieren und SchriftgrÃƒÂ¶ÃƒÅ¸e sowie Farben anpassen.
**Speichern & ÃƒÂ¼bertragen** speichert das Layout und zeigt es auf dem Display.
Ãƒâ€žnderungen ausgewÃƒÂ¤hlter HA-Werte aktualisieren Display und Vorschau automatisch.
Die Verbindung wird zusÃƒÂ¤tzlich alle zehn Sekunden geprÃƒÂ¼ft.

**Element entfernen** neben **Element hinzufÃƒÂ¼gen** lÃƒÂ¶scht das ausgewÃƒÂ¤hlte Element.
Die Ãƒâ€žnderung mit **Speichern & ÃƒÂ¼bertragen** dauerhaft ÃƒÂ¼bernehmen.

Buttons unterstÃƒÂ¼tzen `button`, `input_button`, `script` und `lock` (Aktion `lock.open`); Switches unterstÃƒÂ¼tzen
`switch` und `input_boolean`. Aktionen werden nur durch Tippen am physischen Display
ausgelÃƒÂ¶st. Die Editor-Vorschau ist ausschlieÃƒÅ¸lich zum Gestalten.

Der MVP unterstÃƒÂ¼tzt eine normale Seite pro Display und ein optionales Klingel-
Overlay. Pro Ansicht lÃƒÂ¤uft ein Videofeld.

## Optionales Klingel-Overlay ab 0.6.4

Im Designer **Klingel-Overlay (optional)** aufklappen, aktivieren und auswÃƒÂ¤hlen:

- **Klingel-AuslÃƒÂ¶ser**: `binary_sensor`, `event` oder `input_button`.
- **Overlay-Kamera**: eine vorhandene HA-Kamera.
- **TÃƒÂ¼rÃƒÂ¶ffner / Nuki-Schloss**: `button`, `input_button`, `script` oder `lock`.
  Schloss-EntitÃƒÂ¤ten verwenden `lock.open` zum Ãƒâ€“ffnen der Falle. Das Schloss muss
  diese Funktion ohne PIN unterstÃƒÂ¼tzen; andernfalls ein passendes HA-Skript wÃƒÂ¤hlen.
- **Overlay-Kamera vorbereiten**: optional, standardmÃƒÂ¤ÃƒÅ¸ig aus. HA hÃƒÂ¤lt ein aktuelles
  Kamerabild bereit und verwendet beim Klingeln den bereits laufenden Decoder.
  ZusÃƒÂ¤tzliche Kamera-Verbindung und Rechenlast auf dem HA-Host; keine Standby-
  VideoÃƒÂ¼bertragung zum Display. Nach dem Speichern den ersten Kamerastart abwarten.
  Bis zu zwei Decoder (normales Videofeld und vorbereitete Overlay-Kamera).
  Ab 0.6.4 wird parallel ein HA-Kamerabild vorbereitet, solange der Decoder noch
  keinen aktuellen Streamframe liefert. Es wird hÃƒÂ¶chstens alle zwei Sekunden
  nach Abschluss des letzten Abrufs neu angefragt; bei laufendem Stream entfallen
  diese Abrufe. Das Overlay verwendet das vorbereitete Bild und wechselt danach
  zum Stream. Streamframes gelten 2,5 Sekunden, HA-Kamerabilder fÃƒÂ¼nf Sekunden als
  verwendbar. Die Anzeige **Kamera bereit** meldet Quelle und Empfangsalter.
  Sie bestÃƒÂ¤tigt den Empfang, nicht das Aufnahmealter eines von HA gecachten Bildes.
  Ohne verfÃƒÂ¼gbares Bild kann auch dieser Modus keine sofortige Ansicht garantieren.
  Beim Entladen oder Deaktivieren endet die Vorbereitung; veraltete Bereitschaftsbilder
  werden nicht als erstes Overlay-Bild verwendet.
- **Automatisch schlieÃƒÅ¸en nach**: 5Ã¢â‚¬â€œ300 Sekunden, standardmÃƒÂ¤ÃƒÅ¸ig 30.

Ab 0.6.4 zeigt der TÃƒÂ¼rknopf **Wird geÃƒÂ¶ffnet**, **Befehl ausgefÃƒÂ¼hrt**, **Fehler**
oder bei Timeout **Ergebnis unklar**. Die RÃƒÂ¼ckmeldung bestÃƒÂ¤tigt die Verarbeitung
in HA, nicht den physischen Durchgang. Optional einen **TÃƒÂ¼rkontakt** auswÃƒÂ¤hlen:
`binary_sensor` Ein = TÃƒÂ¼r offen, Aus = geschlossen. Fehlender/unverfÃƒÂ¼gbarer Kontakt
zeigt einen unbekannten Status. Ohne Kontakt wird bei Schloss-EntitÃƒÂ¤ten der
Schlosszustand angezeigt; Ã¢â‚¬Å¾entriegeltÃ¢â‚¬Å“ bedeutet nicht, dass die TÃƒÂ¼r offen steht.

**Nach TÃƒÂ¼raktion mindestens weiter anzeigen** stellt 5Ã¢â‚¬â€œ300 Sekunden ein,
standardmÃƒÂ¤ÃƒÅ¸ig 45. Der Timer startet nach der Aktion erneut; eine bereits lÃƒÂ¤ngere
Restlaufzeit wird nicht verkÃƒÂ¼rzt. Wiederholtes Antippen innerhalb von drei Sekunden
und TÃƒÂ¼raktionen bei offenem Kontakt werden ignoriert. Unsichere oder fehlgeschlagene
Aktionen werden niemals automatisch wiederholt.

Mit **Speichern & ÃƒÂ¼bertragen** ÃƒÂ¼bernehmen. **Overlay-Vorschau** ÃƒÂ¶ffnet nur die
Editor-Vorschau. **Overlay am Display testen** zeigt die gespeicherte Ansicht am
GerÃƒÂ¤t und lÃƒÂ¶st keine TÃƒÂ¼raktion aus. Die TÃƒÂ¼r wird ausschlieÃƒÅ¸lich durch Antippen
des TÃƒÂ¼rÃƒÂ¶ffner-Buttons am Display betÃƒÂ¤tigt. Fehlende/unverfÃƒÂ¼gbare Aktionen bleiben
inaktiv. Bei aktivem Overlay werden Hintergrund-Buttons nicht bedient.

Ein Binary-Sensor lÃƒÂ¶st bei Aus Ã¢â€ â€™ Ein aus. Ereignis-/Input-Button-EntitÃƒÂ¤ten lÃƒÂ¶sen
bei einem neuen aktuellen Zeitstempel aus; alte wiederhergestellte Zeitstempel
und das bloÃƒÅ¸e Initialisieren einer EntitÃƒÂ¤t zeigen kein Overlay. WÃƒÂ¤hle die
Klingel-/Besucher-EntitÃƒÂ¤t und nicht den Bewegungsmelder. Wiederholtes Klingeln
startet die RÃƒÂ¼ckkehrzeit neu. Nach Ablauf wird das normale Layout wieder angezeigt.

Die erste Overlay-Vorlage hat feste Positionen: ÃƒÅ“berschrift, Kamera (432 Ãƒâ€” 180)
und TÃƒÂ¼rÃƒÂ¶ffner. Die normale Anzeige bleibt frei gestaltbar inklusive GrÃƒÂ¶ÃƒÅ¸enÃƒÂ¤nderung.
Ein vorhandener Hintergrund-Stream pausiert wÃƒÂ¤hrend des Overlays; sein letztes
Bild bleibt als Hintergrund, danach startet er neu. Ohne Kameravorbereitung oder
bei fehlendem aktuellem Frame kann zunÃƒÂ¤chst der Offline-Platzhalter sichtbar sein.
Die Vorbereitung verkÃƒÂ¼rzt den erneuten Kamerastart; eine konkrete Latenz hÃƒÂ¤ngt
von Kamera, HA-Host und Netzwerk ab. Die Kamera bleibt bei
hÃƒÂ¶chstens 1 FPS; das Overlay wird bei einem HA-Neustart nicht wiederhergestellt.
FÃƒÂ¼r dieses Feature mit vorhandener JPEG-Firmware ist kein erneutes Flashen nÃƒÂ¶tig.

## Display-Firmware

Das Display braucht die passende Desk-Display-Firmware und muss ÃƒÂ¼ber WLAN
von HA erreichbar sein. Dieses Repository verteilt ausschlieÃƒÅ¸lich die
HA-Integration; Firmware und deren Entwicklung werden separat verwaltet.
Die Hersteller-Demo ist nicht kompatibel. HACS flasht keine ESP32-Firmware.

**Touch benÃƒÂ¶tigt Firmware 0.2.0.** Nach dem Flashen die angezeigten Eckmarkierungen
antippen. Die Kalibrierung wird gespeichert. FÃƒÂ¼r eine erneute Kalibrierung BOOT
am bereits laufenden Display drei Sekunden gedrÃƒÂ¼ckt halten, dann loslassen.
Ãƒâ€žltere Firmware unterstÃƒÂ¼tzt weiterhin Texte und HA-Werte.

HA holt Touch-Ereignisse etwa einmal pro Sekunde ab. Jeder Druck lÃƒÂ¶st hÃƒÂ¶chstens
eine Aktion aus; lange gehaltene BerÃƒÂ¼hrungen werden nicht wiederholt. Veraltete
Ereignisse, andere Layoutversionen und nicht verfÃƒÂ¼gbare EntitÃƒÂ¤ten werden verworfen.
Eine wegen Verbindungsverlust oder ZeitÃƒÂ¼berschreitung unsichere Aktion wird nicht
automatisch wiederholt. Der Switch-Zustand kommt immer aus HA.

## Ruhigere Bildupdates und Debug-Anzeige (Firmware 0.3.0)

Neue Firmware empfÃƒÂ¤ngt ein komprimiertes Bild bzw. den geÃƒÂ¤nderten Bildbereich
vollstÃƒÂ¤ndig, bevor sie ihn ÃƒÂ¼ber SPI zeichnet. Dadurch wird der Bildschirm nicht
mehr wÃƒÂ¤hrend des langsamen WLAN-Empfangs zeilenweise aufgebaut. Normale
WertÃƒÂ¤nderungen ÃƒÂ¼bertragen nur den betroffenen Bereich. FÃƒÂ¼r schlecht komprimierbare
Bilder gibt es einen begrenzten, gepufferten Streifenmodus. Es gibt keinen
vollstÃƒÂ¤ndigen Bildpuffer und keine Zusage fÃƒÂ¼r vÃƒÂ¶llig unsichtbare SPI-Bildwechsel.

Im Designer **CPU und FPS anzeigen** aktivieren und **Speichern & ÃƒÂ¼bertragen**
drÃƒÂ¼cken. Das lokale Overlay erscheint unten rechts (224 Ãƒâ€” 20 Pixel). Deaktivieren
und speichern blendet es wieder aus; die Einstellung bleibt in HA gespeichert.
Keine zusÃƒÂ¤tzlichen HA-Bildupdates werden fÃƒÂ¼r das Overlay erzeugt.

- **CPU~**: statistische NÃƒÂ¤herung der mittleren BeschÃƒÂ¤ftigung beider ESP32-Kerne,
  durch Abtasten der laufenden Tasks gegenÃƒÂ¼ber den Idle-Tasks etwa 997-mal pro Sekunde.
- **FPS**: vollstÃƒÂ¤ndig abgeschlossene HA-Bildupdates pro Sekunde, gemittelt ÃƒÂ¼ber
  fÃƒÂ¼nf Sekunden. Die Debug-Anzeige selbst und einzelne Teilbereiche zÃƒÂ¤hlen nicht.
  Bei unverÃƒÂ¤nderten Daten sind 0 FPS korrekt; dies ist nicht die Scanfrequenz des TFT.

Die Messung wird ausgeschaltet, wenn das Overlay deaktiviert ist. Unter dem Overlay
liegende Buttons reagieren in dieser Ecke nicht auf Touch. Ãƒâ€žltere Firmware kann
weiterhin Texte und HA-Werte anzeigen, unterstÃƒÂ¼tzt aber diese Verbesserungen nicht.

## Video / Livestream

### GrÃƒÂ¶ÃƒÅ¸ere Videos und GrÃƒÂ¶ÃƒÅ¸enÃƒÂ¤nderung ab 0.5.0

Mit Integration **0.5.0** und Firmware **0.5.0** lassen sich alle Elemente am Griff
unten rechts vergrÃƒÂ¶ÃƒÅ¸ern/verkleinern. Position und GrÃƒÂ¶ÃƒÅ¸e bleiben auf das Display
begrenzt. Die Zahlenfelder stehen ebenfalls weiterhin zur VerfÃƒÂ¼gung.

Videofelder kÃƒÂ¶nnen bis **480 Ãƒâ€” 320 Pixel** groÃƒÅ¸ sein. Der JPEG-Transport verwendet
den vorhandenen 64-KiB-Puffer des ESP32; kein Vollbildpuffer und kein PSRAM nÃƒÂ¶tig.
Video wird unabhÃƒÂ¤ngig vom zehnsekÃƒÂ¼ndigen Heartbeat ÃƒÂ¼bertragen; alte Frames werden
verworfen. Buttons oberhalb des Videos bleiben Teil der Komposition, Touch-Ereignisse
bleiben bei unverÃƒÂ¤nderter Aktionsrevision erhalten. JPEG ist verlustbehaftet;
bei sehr detailreichen Bildern wird die QualitÃƒÂ¤t an den begrenzten Puffer angepasst.

Ab Integration **0.5.1** sind Streams fest auf **hÃƒÂ¶chstens 1 FPS** begrenzt, auch
bei ÃƒÂ¤lteren gespeicherten Layouts mit hÃƒÂ¶herer Zielbildrate. HA-Werte und Touch-
Aktionen werden unabhÃƒÂ¤ngig vom Videotakt verarbeitet. Es werden weiterhin die
neuesten verfÃƒÂ¼gbaren Bilder verwendet und alte Frames verworfen. Bei langsamer
Quelle oder Verbindung kann die Bildrate niedriger sein. Der FPS-ZÃƒÂ¤hler zÃƒÂ¤hlt
auch andere BildÃƒÂ¤nderungen; solche Updates kÃƒÂ¶nnen ihn ÃƒÂ¼ber 1 steigen lassen.

FÃƒÂ¼r grÃƒÂ¶ÃƒÅ¸ere Videos **Firmware 0.5.0 oder neuer flashen**, dabei
`include/secrets.h` behalten. AnschlieÃƒÅ¸end HA/HACS aktualisieren, HA neu starten,
Designer neu laden und speichern. Vorhandene Touchkalibrierung bleibt erhalten.
FÃƒÂ¼r die Begrenzung auf 1 FPS genÃƒÂ¼gt das HACS-Update; Firmware 0.3.0 unterstÃƒÂ¼tzt
weiterhin kleine Streams bis 160 Ãƒâ€” 120 Pixel, ebenfalls mit hÃƒÂ¶chstens 1 FPS.

### Erster Stream-MVP (0.4.x)

Firmware **0.3.0 reicht aus**. Nach dem HACS-Update Home Assistant vollstÃƒÂ¤ndig
neu starten und den Designer neu laden. Ein Element hinzufÃƒÂ¼gen und den Typ
**Video / Livestream** auswÃƒÂ¤hlen. Eine vorhandene HA-Kamera auswÃƒÂ¤hlen, mit
**HA-Medien auswÃƒÂ¤hlen** die Medienbibliothek ÃƒÂ¶ffnen oder eine direkte Video-URL
eintragen. Position und GrÃƒÂ¶ÃƒÅ¸e festlegen und **Speichern & ÃƒÂ¼bertragen** drÃƒÂ¼cken.

HA lÃƒÂ¶st `camera.*` und `media-source://Ã¢â‚¬Â¦` auf. Ein dauerhaft laufender FFmpeg-Prozess
dekodiert das Video auÃƒÅ¸erhalb des HA-Eventloops. RTSP(S), HTTP(S) (z. B. HLS,
MJPEG, MP4) und RTMP(S) kÃƒÂ¶nnen verwendet werden, soweit die installierte FFmpeg-
Version die konkrete Quelle und deren Codec unterstÃƒÂ¼tzt. Kamera-Zugangsdaten
kommen aus der bestehenden HA-Integration; HA-Tokens werden nicht ans Display
ÃƒÂ¼bertragen. Ein Kamera-Substream verringert die Last auf dem HA-Host.

Der erste Stream-MVP unterstÃƒÂ¼tzt **ein Videofeld bis 160 Ãƒâ€” 120 Pixel**, **ohne Ton**,
mit **Ziel 2 FPS**. Jeder Video-Bildbereich passt vollstÃƒÂ¤ndig in den Displaypuffer.
Die reale Bildrate hÃƒÂ¤ngt von Netzwerk, Quelle und HA-Host ab. Bei langsamer
ÃƒÅ“bertragung werden alte Frames verworfen; es wird keine wachsende Warteschlange
aufgebaut. Die Vorschau zeigt etwa einmal pro Sekunde den letzten dekodierten
Frame der gespeicherten Quelle. Buttons kÃƒÂ¶nnen oberhalb des Videos liegen;
Videobewegung verÃƒÂ¤ndert die Aktionszuordnung nicht.

Das ist ein laufender Videostream, kein wiederholter Kamera-Snapshot-Aufruf.
Bei Streamverlust erscheint **Stream offline**, danach erfolgt ein neuer Versuch
nach zehn Sekunden. Endliche Dateien starten nach dem Ende erneut. Entfernen
oder Ãƒâ€žndern der Quelle sowie Entladen der Integration beendet den alten Decoder.

**Nicht abspielbar:** normale Webseiten, DRM-geschÃƒÂ¼tzte Inhalte, reine Audioquellen
und reine WebRTC-Kameras ohne abrufbare Videoquelle. Eine sichtbare Kamera in HA
allein garantiert deshalb noch keinen kompatiblen Stream. GrÃƒÂ¶ÃƒÅ¸ere Videoansichten
und hÃƒÂ¶here Bildraten benÃƒÂ¶tigen einen weiteren Ausbau des Transports.

## Kommunikation und Support

### Streamdiagnose ab 0.4.1

Der Designer zeigt bei der ausgewÃƒÂ¤hlten gespeicherten Videoquelle den Status und
eine eingegrenzte Fehlermeldung, etwa fehlende Kamera-Stream-URL, Anmeldung
abgelehnt, Quelle nicht erreichbar, Timeout oder Decoder-/Formatfehler.
FFmpeg-Ausgaben werden nur begrenzt intern ausgewertet; URLs, PasswÃƒÂ¶rter und Tokens
erscheinen nicht in diesen Meldungen oder Logs. RTSP verwendet den
protokollspezifischen TCP-Timeout statt der allgemeinen HTTP-Timeout-Option.

Die Integration nutzt die vorhandenen HA-EntitÃƒÂ¤ten und kommuniziert lokal
mit dem Display auf Port 80. Der GerÃƒÂ¤teschlÃƒÂ¼ssel wird in HA gespeichert.
Keine HA-Zugangsdaten werden auf das Display ÃƒÂ¼bertragen. Das Display ist
fÃƒÂ¼r das Heimnetz vorgesehen; Port 80 nicht ins Internet weiterleiten.

Fehler kÃƒÂ¶nnen unter [Issues](https://github.com/rbnstn/ha-desk-display-hacs/issues)
gemeldet werden. Bitte keine PasswÃƒÂ¶rter, GerÃƒÂ¤teschlÃƒÂ¼ssel oder HA-Tokens posten.

Dies ist das ÃƒÂ¶ffentliche Installationsrepository. Die Entwicklung und Tests
finden in einem separaten privaten Repository statt. Es werden nur ausgewÃƒÂ¤hlte
Integrationsdateien verÃƒÂ¶ffentlicht, keine private Entwicklungshistorie.

## Material-Design ab 0.7.0

Im Designer unter **Display-Design** zwischen Klassisch, Material Ã‚Â· Dunkel und
Material Ã‚Â· Hell wÃƒÂ¤hlen. Speichern & ÃƒÂ¼bertragen ÃƒÂ¼bernimmt das Design. Positionen,
GrÃƒÂ¶ÃƒÅ¸en und EntitÃƒÂ¤ten bleiben erhalten; Hintergrund und Textfarben werden beim
Designwechsel gesetzt. Bestehende Layouts bleiben zunÃƒÂ¤chst klassisch.

Material bietet Karten fÃƒÂ¼r HA-Werte, zentrierte Buttons, Schiebeschalter und
abgerundete Videofelder. Pro Element lassen sich KartenflÃƒÂ¤che, Kartenfarbe,
Eckenradius und Textausrichtung anpassen. Ab 62 Pixel HÃƒÂ¶he erscheinen Sensorlabel
und Wert auf getrennten Zeilen. Das optionale Klingel-Overlay folgt dem Design.
Die Darstellung entsteht in HA; die Firmware und das Limit von 1 FPS bleiben
unverÃƒÂ¤ndert. Nach dem HACS-Update HA neu starten und den Designer neu laden
(gegebenenfalls Strg+F5). Kein Firmware-Update erforderlich.

## Layout-Werkzeuge ab 0.7.1

Unter **Anordnen** das ausgewÃƒÂ¤hlte Element duplizieren, eine Ebene nach vorn oder
zurÃƒÂ¼ck verschieben und am gesamten Display ausrichten. Duplikate ÃƒÂ¼bernehmen
EntitÃƒÂ¤t, Stil und GrÃƒÂ¶ÃƒÅ¸e und werden innerhalb des Displays leicht versetzt.
Die oberste Ebene bestimmt auch das Touch-Ziel. Videofelder lassen sich nicht
duplizieren, da weiterhin eine Videoquelle pro Ansicht unterstÃƒÂ¼tzt wird.
AnschlieÃƒÅ¸end **Speichern & ÃƒÂ¼bertragen**. Kein Firmware-Update erforderlich.

## Werte, Uhrzeit und Bilder ab 0.8.0

HA-Werte zeigen die Beschriftung links und den Wert rechts. Bei hohen Karten
stehen beide auf getrennten Zeilen. Im Designer sind Umrechnungsfaktor, eigene
Einheit, Nachkommastellen und Vorzeichenwechsel einstellbar. Beispiel: Faktor
0,001 + Einheit kW rechnet 2500 W in 2,5 kW um. Vorzeichenwechsel multipliziert
zusÃƒÂ¤tzlich mit -1. Eine leere eigene Einheit blendet die Einheit aus; der Button
**HA-Einheit verwenden** stellt die ursprÃƒÂ¼ngliche Einheit wieder her. Diese
Ãƒâ€žnderungen betreffen nur die Anzeige, nicht die HA-EntitÃƒÂ¤t.

Eine optionale Ersatz-EntitÃƒÂ¤t ÃƒÂ¼bernimmt die Anzeige bei 0, fehlendem Wert oder
beidem. GeprÃƒÂ¼ft wird der ursprÃƒÂ¼ngliche HA-Wert vor der Umrechnung; fehlend sind
unbekannt, nicht verfÃƒÂ¼gbar, null oder leer. Auch Ãƒâ€žnderungen des Ersatzwerts lÃƒÂ¶sen
eine Aktualisierung aus. Ist der Ersatz ebenfalls nicht verfÃƒÂ¼gbar, erscheint
Nicht verfÃƒÂ¼gbar. Umrechnung und eigene Einheit gelten auch fÃƒÂ¼r den Ersatz.

Neue Elementtypen **Uhrzeit / Datum** und **Bild / Logo** lassen sich frei
positionieren und vergrÃƒÂ¶ÃƒÅ¸ern. Die Uhr verwendet die HA-Zeitzone und zeigt Minuten;
sie aktualisiert sich spÃƒÂ¤testens etwa zehn Sekunden nach dem Minutenwechsel.
Bilder als PNG, JPEG oder WebP hochladen (maximal 5 MB Eingabe); der Designer
verkleinert sie auf maximal 480 Ãƒâ€” 320 und 100 KB. Transparente PNG-Logos werden
unterstÃƒÂ¼tzt. VollstÃƒÂ¤ndige Anzeige oder zugeschnittenes FÃƒÂ¼llen ist wÃƒÂ¤hlbar. Bilder
werden im Layout gespeichert; externe Bild-URLs und SVG sind nicht unterstÃƒÂ¼tzt.
Nach dem HACS-Update HA neu starten und den Designer mit Strg+F5 neu laden.
Kein Firmware-Update erforderlich.

## Kompakter Designer ab 0.9.0

Vorschau und Speichern bleiben im sichtbaren Arbeitsbereich. Rechts scrollen
nur die Einstellungen. Die Reiter **Element**, **Display** und **Klingel** trennen
Elementdaten von allgemeinen Einstellungen und dem optionalen Overlay.
Anordnen, Umrechnung & Ersatzwert, Position & GrÃƒÂ¶ÃƒÅ¸e und Aussehen sind aufklappbar.
GeÃƒÂ¶ffnete Gruppen bleiben wÃƒÂ¤hrend der Bearbeitung erhalten.

Die Elementleiste unter der Vorschau ermÃƒÂ¶glicht einen schnellen Wechsel;
Umbenennungen erscheinen sofort in Leiste und Auswahl. Das markierte Element
lÃƒÂ¤sst sich nach Fokussieren des Vorschaufelds mit Pfeiltasten um 1 Pixel bewegen,
mit Shift um 10 Pixel. Ziehen und der grÃƒÂ¼ne Griff fÃƒÂ¼r GrÃƒÂ¶ÃƒÅ¸enÃƒÂ¤nderung bleiben.
Eine Anzeige neben dem Speichern-Button zeigt ungespeicherte Ãƒâ€žnderungen.
Auch Ãƒâ€žnderungen wÃƒÂ¤hrend eines laufenden Speichervorgangs bleiben als
ungespeichert erkennbar; eine ÃƒÂ¤ltere Speichervorschau ÃƒÂ¼berschreibt sie nicht.
Der Designer passt Vorschau und Seitenleiste auch an schmale Fenster an.
Nach dem HACS-Update HA neu starten und den Designer mit Strg+F5 neu laden.
Kein Firmware-Update erforderlich.

## Version 0.10.0: Designer editing tools

RÃ¼ckgÃ¤ngig/Wiederholen mit 40 Schritten, optionales Raster mit Kantenfang, Mehrfachauswahl per Strg/Klick, Gruppieren, gemeinsam verschieben, ausrichten und verteilen. Gruppen werden im Layout gespeichert. Kein Firmware-Update nÃ¶tig.

## Version 0.11.0: State rules

Bedingte Textfarben und Symbol-Präfixe (bis vier Regeln), Sichtbarkeit nach HA-Zustand. Versteckte Elemente haben keine Touch-Aktion. Regeln reagieren auch auf zusätzliche Entitäten und verwenden Rohwerte. Kein Firmware-Update nötig.
