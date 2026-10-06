"""Small, antialiased power-flow diagrams rendered on HA, without animation."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageColor
from .widgets import number

ROLES = ('solar', 'house', 'battery', 'grid', 'battery_soc', 'wallbox')


def power(config, states, role):
    raw, unit = states.get('__raw__', {}).get(config.get(role, ''), ('unavailable', ''))
    value = number(raw)
    if value is None:
        return None
    # Preserve saved explicit factors; new widgets convert each HA unit separately.
    mode = config.get('power_unit', 'factor' if config.get('factor', 1) != 1 else 'auto')
    if mode == 'factor':
        value *= float(config.get('factor', 1))
    elif unit in ('W', '', None):
        pass
    elif unit == 'kW':
        value *= 1000
    else:
        return None
    if role in ('grid', 'battery') and config.get(role + '_invert'):
        value = -value
    return value if math.isfinite(value) else None


def snapshot(config, states):
    values = {role: power(config, states, role) for role in ('solar', 'house', 'grid', 'battery', 'wallbox')}
    raw, unit = states.get('__raw__', {}).get(config.get('battery_soc', ''), ('unavailable', '%'))
    soc = number(raw)
    values['battery_soc'] = soc if soc is not None and 0 <= soc <= 100 and unit in ('%', '', None) else None
    return values


def watts(value):
    if value is None:
        return '—'
    value = abs(value)
    if value >= 1000:
        return (f'{value / 1000:.2f}'.rstrip('0').rstrip('.').replace('.', ',') + ' kW')
    return f'{value:.0f} W'


def tile(widget, states, theme):
    width, height = widget['width'], widget['height']
    config = widget.get('config', {})
    values = snapshot(config, states)
    light = theme == 'material_light'
    palette = {'solar': '#bf8300' if light else '#f5ce46', 'grid': '#2763cf' if light else '#6399ff',
               'house': '#00865a' if light else '#36e6ad', 'battery': '#008b7c' if light else '#36d7c3',
               'wallbox': '#7c43bd' if light else '#b18bfa'}
    background = widget.get('style', {}).get('background', '#f4f7fc' if light else '#151d2a')
    base = ImageColor.getrgb(background)
    scale = 3
    image = Image.new('RGBA', (width * scale, height * scale))
    draw = ImageDraw.Draw(image)

    def mix(color, amount):
        rgb = ImageColor.getrgb(color)
        return tuple(round(a * (1 - amount) + b * amount) for a, b in zip(base, rgb)) + (255,)

    def box(bounds):
        return tuple(round(v * scale) for v in bounds)

    def line(points, color, thickness=1.6):
        draw.line([tuple(round(v * scale) for v in p) for p in points], fill=color,
                  width=max(1, round(thickness * scale)), joint='curve')

    def ellipse(bounds, color, outline=None, thickness=1):
        draw.ellipse(box(bounds), fill=color, outline=outline, width=max(1, round(thickness * scale)))

    def text(center, value, size, color, max_width):
        size = max(7, round(size))
        font = ImageFont.load_default(size=size * scale)
        while size > 7 and font.getlength(value) > max_width * scale:
            size -= 1
            font = ImageFont.load_default(size=size * scale)
        draw.text(tuple(round(v * scale) for v in center), value, font=font, fill=color, anchor='mm')

    draw.rounded_rectangle(box((0, 0, width - 1, height - 1)), radius=min(16, width / 8, height / 8) * scale, fill=background)
    muted = '#526076' if light else '#aab6c9'
    labels = {'solar': 'Solar', 'grid': 'Netz', 'house': 'Haus', 'battery': 'Batterie', 'wallbox': 'Wallbox'}
    roles = ['solar', 'grid', 'battery', 'house'] + (['wallbox'] if config.get('wallbox') else [])

    # Very small old widgets remain legible as bounded cards instead of overlapping circles.
    if width < 240 or height < 150:
        for index, role in enumerate(roles):
            columns = 2 if len(roles) == 4 else 3
            rows = 2
            cell_w, cell_h = width / columns, height / rows
            x, y = (index % columns) * cell_w, (index // columns) * cell_h
            draw.rounded_rectangle(box((x + 2, y + 2, x + cell_w - 3, y + cell_h - 3)), radius=4 * scale, fill=mix(palette[role], .10))
            text((x + cell_w / 2, y + cell_h * .28), labels[role], 9, muted, cell_w - 6)
            label = f'{values["battery_soc"]:.0f} %' if role == 'battery' and config.get('battery_soc') and values['battery_soc'] is not None else watts(values[role])
            if role == 'battery' and config.get('battery_soc') and values['battery_soc'] is None:
                label = '— %'
            text((x + cell_w / 2, y + cell_h * .70), label, min(widget['size'], 12), palette[role], cell_w - 6)
        return image.resize((width, height), Image.Resampling.LANCZOS)

    wallbox = bool(config.get('wallbox'))
    radius = min(width * .14, height * (.16 if wallbox else .18))
    centers = {'solar': (width * .17, height * .25), 'grid': (width * .50, height * (.20 if wallbox else .25)),
               'battery': (width * .83, height * .25), 'house': (width * .50, height * (.63 if wallbox else .74)),
               'wallbox': (width * .17, height * .80)}
    radii = {role: radius * (1.08 if role == 'house' else 1) for role in roles}
    house = centers['house']

    for role in ('solar', 'grid', 'battery', 'wallbox'):
        if role not in roles:
            continue
        start = centers[role]
        if role in ('solar', 'battery'):
            controls = (start, (start[0], house[1]), (house[0], house[1]), house)
        else:
            controls = (start, (start[0], start[1] + (house[1] - start[1]) / 3),
                        (house[0], start[1] + 2 * (house[1] - start[1]) / 3), house)
        path = []
        for i in range(81):
            t = i / 80
            p = tuple((1-t)**3*controls[0][j] + 3*(1-t)**2*t*controls[1][j] + 3*(1-t)*t*t*controls[2][j] + t**3*controls[3][j] for j in (0, 1))
            if math.dist(p, start) > radii[role] + 3 and math.dist(p, house) > radii['house'] + 3:
                path.append(p)
        if len(path) < 2:
            continue
        accent = palette[role]
        line(path, mix(accent, .22), 2.2)
        value = values[role]
        if value is None or abs(value) < 1 or (role == 'solar' and value <= 0):
            continue
        # Positive grid/battery values feed the house, positive wallbox values consume.
        inward = role != 'wallbox' and value > 0 or role == 'wallbox' and value < 0
        if not inward:
            path.reverse()
        a, b = max(0, len(path)//4), max(1, 3*len(path)//4)
        line(path[a:b+1], accent, 3.2)
        for end in (path[a], path[b]):
            ellipse((end[0]-1.6, end[1]-1.6, end[0]+1.6, end[1]+1.6), accent)
        tip, previous = path[b], path[max(0, b-2)]
        dx, dy = tip[0]-previous[0], tip[1]-previous[1]
        length = max(.001, math.hypot(dx, dy));ux, uy = dx/length, dy/length
        arrow = min(5, radius*.16)
        line([(tip[0]-ux*arrow-uy*arrow*.6, tip[1]-uy*arrow+ux*arrow*.6), tip,
              (tip[0]-ux*arrow+uy*arrow*.6, tip[1]-uy*arrow-ux*arrow*.6)], accent, 2)

    def icon(role, center, size, color):
        x, y = center
        def p(a, b): return (x + a * size, y + b * size)
        def stroke(points): line([p(a, b) for a, b in points], color, 1.5)
        if role == 'solar':
            ellipse((x-size*.25, y-size*.25, x+size*.25, y+size*.25), None, color, 1.5)
            for i in range(8):
                angle=i*math.pi/4;stroke([(math.cos(angle)*.38, math.sin(angle)*.38), (math.cos(angle)*.54, math.sin(angle)*.54)])
        elif role == 'house':
            stroke([(-.5, 0), (0, -.45), (.5, 0)])
            stroke([(-.35, -.08), (-.35, .45), (.35, .45), (.35, -.08)])
            stroke([(-.12, .45), (-.12, .1), (.12, .1), (.12, .45)])
        elif role == 'grid':
            stroke([(-.35, .48), (0, -.5), (.35, .48)])
            stroke([(-.28, -.18), (.28, -.18)]);stroke([(-.43, .08), (.43, .08)])
            stroke([(-.5, .48), (.5, .48)]);stroke([(-.18, .25), (.18, .25)])
        elif role == 'battery':
            draw.rounded_rectangle(box((x-size*.29, y-size*.43, x+size*.29, y+size*.45)), radius=2*scale, outline=color, width=round(1.5*scale))
            line([p(-.12, -.53), p(.12, -.53)], color, 2)
            soc = values['battery_soc']
            if soc is not None and soc > 0:
                draw.rectangle(box((x-size*.18, y+size*.32-size*.65*soc/100, x+size*.18, y+size*.32)), fill=color)
            elif soc is None:
                stroke([(.08, -.24), (-.12, .03), (.1, .03), (-.08, .27)])
        else:
            draw.rounded_rectangle(box((x-size*.34, y-size*.45, x+size*.25, y+size*.45)), radius=2*scale, outline=color, width=round(1.5*scale))
            stroke([(.25, -.15), (.48, -.02), (.48, .34), (.3, .34)])
            stroke([(.06, -.25), (-.15, .04), (.05, .04), (-.12, .28)])

    for role in roles:
        x, y = centers[role];r = radii[role];accent = palette[role]
        for halo in (6, 4, 2):
            ellipse((x-r-halo, y-r-halo, x+r+halo, y+r+halo), mix(accent, .035 + (6-halo)*.012))
        ellipse((x-r, y-r, x+r, y+r), mix(accent, .06), mix(accent, .68 if role != 'house' else .95), 1.5 if role != 'house' else 2)
        if role == 'battery' and config.get('battery_soc') and values['battery_soc'] is not None:
            draw.arc(box((x-r, y-r, x+r, y+r)), -90, -90+3.6*values['battery_soc'], fill=accent, width=round(2.2*scale))
        icon(role, (x, y-r*.43), r*.46, accent)
        text((x, y-r*.02), labels[role], max(8, min(11, r*.26)), muted, r*1.65)
        label = watts(values[role])
        if role == 'battery' and config.get('battery_soc'):
            label = '— %' if values['battery_soc'] is None else f'{values["battery_soc"]:.0f} %'
        text((x, y+r*(.32 if role == 'battery' and config.get('battery_soc') else .48)), label, min(widget['size'], r*.43), accent, r*1.65)
        if role == 'battery' and config.get('battery_soc'):
            text((x, y+r*.68), watts(values['battery']), 9, muted, r*1.45)
    return image.resize((width, height), Image.Resampling.LANCZOS)
