"""Package a credential-free firmware binary and its provenance."""
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def package(root=ROOT, destination=None):
    root = Path(root)
    if (root / 'firmware/include/secrets.h').exists():
        raise ValueError('Public firmware must be built without secrets.h')
    source = (root / 'firmware/src/main.cpp').read_text()
    match = re.search(r'kFirmwareVersion\[\]="desk_display_version:([0-9]+\.[0-9]+\.[0-9]+)"', source)
    if not match:
        raise ValueError('Firmware version missing')
    version = match[1]
    binary = (root / 'firmware/.pio/build/e32r35t/firmware.bin').read_bytes()
    marker = f'desk_display_version:{version}'.encode()
    if not 65536 <= len(binary) <= 1310720 or binary[0] != 0xe9 or binary[12:14] != b'\0\0' or b'desk_display:E32R35T:1' not in binary or marker not in binary:
        raise ValueError('Invalid E32R35T firmware binary or version mismatch')
    versions = set(re.findall(rb'desk_display_version:([0-9]+\.[0-9]+\.[0-9]+)', binary))
    if versions != {version.encode()}:
        raise ValueError('Ambiguous firmware version')
    integration = json.loads((root / 'custom_components/desk_display/manifest.json').read_text())['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', integration):
        raise ValueError('Invalid integration version')
    destination = Path(destination or root / 'dist')
    destination.mkdir(parents=True, exist_ok=True)
    name = f'desk-display-e32r35t-{version}.bin'
    digest = hashlib.sha256(binary).hexdigest()
    (destination / name).write_bytes(binary)
    (destination / (name + '.sha256')).write_text(f'{digest}  {name}\n')
    metadata = {'model': 'E32R35T', 'firmware_version': version, 'integration_version': integration,
                'source_commit': os.environ.get('GITHUB_SHA', ''), 'sha256': digest,
                'size_bytes': len(binary), 'credentials_embedded': False,
                'platformio': '6.1.18', 'environment': 'e32r35t'}
    (destination / (name + '.json')).write_text(json.dumps(metadata, indent=2) + '\n')
    build=root/'firmware/.pio/build/e32r35t'
    boot_app=Path(os.environ.get('DESK_BOOT_APP0',str(Path.home()/'.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin')))
    sources=[('bootloader.bin',build/'bootloader.bin',4096),('partitions.bin',build/'partitions.bin',32768),('boot_app0.bin',boot_app,57344),(name,build/'firmware.bin',65536)]
    factory=bytearray(b'\xff'*(65536+len(binary)))
    parts=[]
    for filename,path,offset in sources:
        data=path.read_bytes()
        limit=next((position for _,_,position in sources if position>offset),len(factory))
        if not data or offset+len(data)>limit:raise ValueError('Invalid boot partition sizes')
        target=filename if filename==name else f'desk-display-e32r35t-{version}-'+filename
        (destination/target).write_bytes(data)
        factory[offset:offset+len(data)]=data
        parts.append({'path':target,'offset':offset})
    factory_name=f'desk-display-e32r35t-{version}-factory.bin'
    (destination/factory_name).write_bytes(factory)
    (destination/(factory_name+'.sha256')).write_text(hashlib.sha256(factory).hexdigest()+'  '+factory_name+'\n')
    manifest={'name':'Desk Display E32R35T','version':version,'new_install_prompt_erase':True,'builds':[{'chipFamily':'ESP32','parts':parts}]}
    (destination/'web-install-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return metadata


if __name__ == '__main__':
    result = package()
    print(json.dumps(result))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f"version={result['firmware_version']}\ntag=v{result['integration_version']}\n")
