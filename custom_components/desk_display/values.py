"""Pure display-only sensor formatting; never modifies Home Assistant states."""
import math


def numeric(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def sensor_value(widget, states):
    options = widget.get('value', {})
    entity = widget['entity_id']
    raw = states.get('__raw__', {})
    if entity not in raw:
        return states.get(entity, 'Nicht verfuegbar')
    value, unit = raw[entity]
    missing = str(value).lower() in ('unknown', 'unavailable', 'none', 'null', '')
    mode = options.get('fallback_mode', 'both')
    if options.get('fallback_entity_id') and ((missing and mode in ('missing','both')) or
                                             (numeric(value) == 0 and mode in ('zero','both'))):
        value, unit = raw.get(options['fallback_entity_id'], ('unavailable', ''))
    if str(value).lower() in ('unknown', 'unavailable', 'none', 'null', ''):
        return 'Nicht verfuegbar'
    number = numeric(value)
    if number is not None:
        factor = options.get('factor', 1) * (-1 if options.get('invert', False) else 1)
        number *= factor
        if not math.isfinite(number):
            return 'Nicht verfuegbar'
        unit = options.get('unit', unit)
        if options.get('auto_power') and unit in ('W','kW'):
            watts = number * (1000 if unit == 'kW' else 1)
            number, unit = (watts / 1000, 'kW') if abs(watts) >= 1000 else (watts, 'W')
            value = f'{0 if number == 0 else number:.{options.get("decimals",2) if unit == "kW" else 0}f}'
        elif 'decimals' in options:
            number = round(number, options['decimals'])
            value = f"{0 if number == 0 else number:.{options['decimals']}f}"
        elif factor != 1:
            value = f'{0 if number == 0 else number:g}'
        if options.get('decimal_separator') == ',':
            value = str(value).replace('.', ',')
    return f'{value} {unit}'.strip()[:120]
