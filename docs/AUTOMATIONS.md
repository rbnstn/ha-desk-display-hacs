# Hinweise und Automationen / Notifications and automations

[Deutsch](../README.md) · [English](../README.en.md)

## Deutsch

Einfache Meldungen können direkt unter **Display → Hinweise & Meldungen** konfiguriert werden. Vergleiche den ursprünglichen HA-Wert: bei einem Leistungssensor in W beispielsweise `gt` und `3000`. Die Formatierung im Display ändert den Vergleichswert nicht. Hysterese und Verzögerung vermeiden Meldungen bei kurzen Schwankungen. Eine neue Regel wird zunächst mit dem aktuellen Zustand initialisiert und meldet erst beim nächsten Wechsel von nicht erfüllt zu erfüllt.

Für komplexere Abläufe die HA-Aktion **Desk Display: Meldung anzeigen** verwenden. `device_id` ist die Home-Assistant-Geräte-ID, nicht die IP-Adresse und nicht der Geräteschlüssel. Wähle das Zielgerät im Automationseditor oder ersetze den Platzhalter. Bei Serviceaufrufen entsteht eine neue Meldung; wiederholte Aufrufe können sie erneut anzeigen.

```yaml
alias: Fensterhinweis am Desk Display
triggers:
  - trigger: state
    entity_id: binary_sensor.fenster
    to: "on"
    for: "00:00:30"
actions:
  - action: desk_display.notify
    data:
      device_id: "DEINE_HA_GERAETE_ID"
      message: "Das Fenster ist noch geöffnet"
      duration: 20
      priority: 1
mode: single
```

Meldungen laufen nach 5 bis 300 Sekunden ab. Priorität 0 bis 3: höhere Priorität wird zuerst angezeigt; die Warteschlange ist auf fünf Meldungen begrenzt. Die Klingelansicht hat Vorrang. Eine abgelaufene Meldung wird danach nicht erneut angezeigt.

Eine bestimmte Seite vorübergehend anzeigen:

```yaml
action: desk_display.show_page
data:
  device_id: "DEINE_HA_GERAETE_ID"
  page: 1
  duration: 30
```

Seiten beginnen bei 0: `0` ist die Hauptseite, `1` die zweite Seite. Nach der Dauer erscheint die vorherige Seite. Beispielideen: Waschmaschine wechselt auf „fertig“, Türkontakt bleibt 30 Sekunden offen, Netzbezug übersteigt 3 kW für 10 Sekunden. Verwende die Zustände und Einheiten deiner tatsächlichen Sensoren.

## English

Configure simple alerts under **Display → Hinweise & Meldungen**. Conditions compare the original HA reading: use `gt` and `3000` for a power sensor measured in W. Display formatting does not change the comparison. Hysteresis and delay filter brief fluctuations. New rules initialise from the current state and fire only on the next false-to-true transition.

For more complex flows, use the HA action **Desk Display: Meldung anzeigen**. `device_id` means the Home Assistant device ID, not its IP address or device key. Select the target in HA's automation editor or replace the placeholder. Each service invocation creates a notification; repeated calls may show it again.

```yaml
alias: Window notification on Desk Display
triggers:
  - trigger: state
    entity_id: binary_sensor.window
    to: "on"
    for: "00:00:30"
actions:
  - action: desk_display.notify
    data:
      device_id: "YOUR_HA_DEVICE_ID"
      message: "The window is still open"
      duration: 20
      priority: 1
mode: single
```

Duration is 5–300 seconds. Priority is 0–3: higher priority is displayed first; the queue holds up to five messages. The doorbell screen takes precedence. Expired notifications are not replayed afterwards.

To show a page temporarily:

```yaml
action: desk_display.show_page
data:
  device_id: "YOUR_HA_DEVICE_ID"
  page: 1
  duration: 30
```

Pages are zero-based: `0` is the main page, `1` the second. The previous page returns after the configured duration. Useful triggers include an appliance finishing, a window remaining open, or grid import exceeding a threshold. Use your own sensor states and units.
