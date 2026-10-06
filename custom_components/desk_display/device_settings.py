"""Validated brightness schedules and bounded ESP32 firmware files."""
import re

DEFAULT={'brightness':100,'night_enabled':False,'night_start':'22:00','night_end':'07:00','night_brightness':15,'ring_brightness':100,'sleep_after':0,'sleep_brightness':0,'notice_wake_priority':2}
MARKER=b'desk_display:E32R35T:1'

def validate_settings(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULT):raise ValueError('Ungueltige Displayeinstellungen')
    result={**DEFAULT,**value}
    for key in ('brightness','night_brightness','ring_brightness','sleep_brightness'):
        if type(result[key]) is not int or not 0<=result[key]<=100:raise ValueError('Helligkeit: 0 bis 100 Prozent')
    if type(result['notice_wake_priority']) is not int or not 0<=result['notice_wake_priority']<=4:raise ValueError('Aufweckpriorität: 0 bis 3; 4 deaktiviert')
    if type(result['sleep_after']) is not int or (result['sleep_after']!=0 and not 15<=result['sleep_after']<=3600):raise ValueError('Ruhemodus: 0 oder 15 bis 3600 Sekunden')
    if type(result['night_enabled']) is not bool:raise ValueError('Ungueltiger Nachtmodus')
    for key in ('night_start','night_end'):
        if not isinstance(result[key],str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',result[key]):raise ValueError('Uhrzeit im Format HH:MM')
    return result

def brightness(settings,now,ring=False):
    settings=validate_settings(settings)
    if ring:return settings['ring_brightness']
    value=settings['brightness']
    if settings['night_enabled']:
        time=now.strftime('%H:%M');start,end=settings['night_start'],settings['night_end']
        night=start<=time<end if start<end else (time>=start or time<end) if start!=end else False
        if night:value=settings['night_brightness']
    return value

def validate_firmware(data):
    if not isinstance(data,bytes) or not 65536<=len(data)<=1310720 or data[0]!=0xe9 or data[12:14]!=b'\0\0' or MARKER not in data:
        raise ValueError('Bitte eine passende E32R35T Desk-Display-Firmware (.bin, maximal 1,25 MiB) verwenden')
    return data

