"""Text measurements use the same Pillow fonts and insets as the renderer."""
from PIL import ImageFont
from .values import sensor_value


def inspect_text(layout, states_by_page):
    issues, sizes = [], []
    for page_index, page in enumerate([layout, *layout.get('pages', [])]):
        states = states_by_page[page_index]
        for index, widget in enumerate(page['widgets']):
            kind = widget['kind']
            if kind not in ('text', 'sensor', 'button', 'switch'):
                continue
            if widget.get('inherit_design', True):
                size = layout.get('design', {}).get('size', widget['size'])
            else:
                size = widget['size']
            material = page.get('theme') in ('material_dark', 'material_light') or kind == 'sensor'
            surface = widget.get('style', {}).get('surface', kind != 'text') if material else kind in ('button', 'switch')
            inset = min(12, max(0, (widget['width']-1)//4)) if surface and material else 8 if surface else 0
            available = widget['width'] - 2*inset
            label = widget['text'] or (widget['entity_id'] if kind in ('button', 'switch') else '')
            measurements = []
            if kind == 'sensor':
                value = sensor_value(widget, states)
                reserve = '-9999,99 ' + widget.get('value', {}).get('unit', states.get('__raw__', {}).get(widget['entity_id'], ('', ''))[1])
                if label and widget['height'] >= 62:
                    measurements.append((label, min(14, size), available))
                    measurements.append((max((value, reserve), key=len), size, available))
                elif label:
                    measurements.extend([(label, min(16, size), available*.45-4), (max((value, reserve), key=len), size, available*.55-4)])
                else:
                    measurements.append((max((value, reserve), key=len), size, available))
            else:
                if kind == 'switch' and material:
                    available -= min(44, widget['width']//3)+8
                    label += ' · ?'
                measurements.append((label, size, available))
            clipped = any(ImageFont.load_default(size=font_size).getlength(text) > width for text, font_size, width in measurements)
            suggestion = size
            while suggestion > 12 and any(ImageFont.load_default(size=min(font_size, suggestion)).getlength(text) > width for text, font_size, width in measurements):
                suggestion -= 1
            sizes.append({'page': page_index, 'index': index, 'size': suggestion})
            if clipped:
                issues.append({'page': page_index, 'index': index, 'text': f'Text oder größerer Zahlenwert passt nicht vollständig. Vorschlag: Schriftgröße {suggestion}.', 'error': False})
    return {'issues': issues, 'sizes': sizes}
