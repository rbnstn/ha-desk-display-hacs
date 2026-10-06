"""Desk Display constants."""

DOMAIN = "desk_display"
WIDTH = 480
HEIGHT = 320
PROTOCOL = 1
PLATFORMS = ["binary_sensor", "button", "light", "sensor"]
DEFAULT_LAYOUT = {
    "background": "#101827",
    "widgets": [
        {"kind": "text", "text": "Homelab", "entity_id": "", "x": 24,
         "y": 24, "width": 432, "height": 56, "size": 36, "color": "#ffffff"},
        {"kind": "text", "text": "Bereit fuer Home Assistant", "entity_id": "",
         "x": 24, "y": 100, "width": 432, "height": 40, "size": 22,
         "color": "#57d9b0"},
    ],
}

