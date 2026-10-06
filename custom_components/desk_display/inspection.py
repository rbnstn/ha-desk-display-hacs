"""Text measurements use the same Pillow fonts and insets as the renderer."""
from PIL import ImageFont
from .values import sensor_value
from .rules import resolve_layout


def inspect_text(layout, states_by_page):
    issues, sizes = [], []
    for page_index, page in enumerate([layout, *layout.get('pages', [])]):
        states = states_by_page[page_index]
        for index, original in enumerate(page['widgets']):
            kind = original['kind']
            if kind not in ('text', 'sensor', 'button', 'switch', 'clock'):
                continue
            # Resolve global size, surface and rule symbols just as rendering does,
            # retaining the original page/widget indices for the editor.
            resolved = resolve_layout({**page, 'design': layout.get('design', {}),
                                       'widgets': [{**original, 'hidden': False}]}, states)['widgets']
            if not resolved:
                continue
            widget = resolved[0]
            size = widget['size']
            material = page.get('theme') in ('material_dark', 'material_light') or kind in ('sensor', 'clock')
            surface = widget.get('style', {}).get('surface', kind != 'text') if material else kind in ('button', 'switch')
            if page.get('theme') not in ('material_dark', 'material_light') and kind in ('sensor', 'clock'):
                surface = False
            inset = min(12, max(0, (widget['width']-1)//4)) if surface and material else 8 if surface else 0
            available = widget['width'] - 2*inset
            label = widget['text'] or (widget['entity_id'] if kind in ('button', 'switch') else '')
            if kind == 'clock':
                label = states.get('__clock__', {}).get(widget.get('clock_format', 'time'), '--:--')
            measurements = []
            if kind == 'sensor':
                value = sensor_value(widget, states)
                if label and widget['height'] >= 62:
                    measurements.extend([(label, min(14, size), available, 20),
                                         (value, size, available, widget['height']-32)])
                elif label:
                    measurements.extend([(label, min(16, size), available*.45-4, widget['height']),
                                         (value, size, available*.55-4, widget['height'])])
                else:
                    measurements.append((value, size, available, widget['height']))
            else:
                if kind == 'switch' and material:
                    available -= min(44, widget['width']//3)+8
                    if states.get(widget['entity_id'], 'unavailable') in ('Nicht verfuegbar', 'unknown', 'unavailable'):
                        label += ' · ?'
                elif kind == 'switch':
                    value = states.get(widget['entity_id'], 'unavailable')
                    label += ': ' + ('Ein' if value == 'on' else 'Aus' if value == 'off' else '?')
                measurements.append((label, size, available, widget['height']-2*inset if not material else widget['height']))

            def fits(candidate):
                for text, font_size, width, height in measurements:
                    font = ImageFont.load_default(size=min(font_size, candidate))
                    bounds = font.getbbox(text[:160])
                    if max(font.getlength(text[:160]), bounds[2]-bounds[0]) > width or bounds[3]-bounds[1] > height:
                        return False
                return True

            suggestion = size
            while suggestion > 12 and not fits(suggestion):
                suggestion -= 1
            sizes.append({'page': page_index, 'index': index, 'size': suggestion, 'fits': fits(suggestion)})
            if not fits(size):
                message = f'Text passt nicht vollständig. Vorschlag: Schriftgröße {suggestion}.'
                if not fits(suggestion):
                    message += ' Bitte das Element zusätzlich vergrößern.'
                issues.append({'page': page_index, 'index': index, 'text': message, 'error': False})
    return {'issues': issues, 'sizes': sizes}
