"""Resolve touches only against the layout successfully sent by HA."""

import re

BUTTON_SERVICES = {"button": "press", "input_button": "press", "script": "turn_on"}
SWITCH_SERVICES = {"switch": "toggle", "input_boolean": "toggle"}


def action_at(layout, x, y):
    """The topmost rectangle blocks widgets underneath, including plain text."""
    for widget in reversed(layout["widgets"]):
        if widget["x"] <= x < widget["x"] + widget["width"] and (
            widget["y"] <= y < widget["y"] + widget["height"]
        ):
            domain = widget["entity_id"].split(".", 1)[0]
            services = BUTTON_SERVICES if widget["kind"] == "button" else (
                SWITCH_SERVICES if widget["kind"] == "switch" else {})
            service = services.get(domain)
            return (domain, service, widget["entity_id"]) if service else None
    return None


def validate_touch(event):
    if not isinstance(event, dict) or set(event) != {"id", "revision", "x", "y"}:
        raise ValueError("Invalid touch event")
    if not isinstance(event["id"], str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9]{1,10}", event["id"]):
        raise ValueError("Invalid touch ID")
    if not isinstance(event["revision"], str) or not re.fullmatch(r"[0-9a-f]{32}", event["revision"]):
        raise ValueError("Invalid frame revision")
    for key, bound in (("x", 480), ("y", 320)):
        if type(event[key]) is not int or not 0 <= event[key] < bound:
            raise ValueError("Invalid touch position")
    return event
