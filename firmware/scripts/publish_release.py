"""Attach firmware to the matching HACS release without replacing existing binaries."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def gh(*args):
    return subprocess.run(['gh', *args], capture_output=True, text=True, check=False)


def publish():
    repository = os.environ['GITHUB_REPOSITORY']
    destination = Path('dist')
    metadata_files = list(destination.glob('*.bin.json'))
    if len(metadata_files) != 1:
        raise ValueError('Expected exactly one firmware package')
    metadata = json.loads(metadata_files[0].read_text())
    tag = 'v' + metadata['integration_version']
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('Invalid release tag')
    name = metadata_files[0].name.removesuffix('.json')
    binary = destination / name
    if hashlib.sha256(binary.read_bytes()).hexdigest() != metadata['sha256']:
        raise ValueError('Firmware checksum mismatch')
    response = gh('api', f'repos/{repository}/releases/tags/{tag}')
    if response.returncode:
        if 'Not Found' in response.stderr and os.environ.get('GITHUB_EVENT_NAME') != 'release':
            print(f'{tag} is not published yet. Firmware is available as a workflow artifact; publishing the release will build and attach it automatically.')
            return
        raise RuntimeError(response.stderr)
    release = json.loads(response.stdout)
    if release['draft'] or release['prerelease']:
        raise ValueError('Firmware publication requires a normal published HACS release')
    event_tag = os.environ.get('RELEASE_TAG', '')
    if event_tag and event_tag != tag:
        raise ValueError('Release tag does not match the integration manifest')
    existing = {asset['name'] for asset in release['assets']}
    if name in existing:
        with tempfile.TemporaryDirectory() as directory:
            response = gh('release', 'download', tag, '--repo', repository, '--pattern', name, '--dir', directory)
            if response.returncode:
                raise RuntimeError(response.stderr)
            if hashlib.sha256((Path(directory) / name).read_bytes()).hexdigest() != metadata['sha256']:
                raise ValueError('A different binary already exists for this firmware version. Bump the firmware version; existing downloads are never overwritten.')
    files = [str(path) for path in sorted(destination.iterdir()) if path.name not in existing]
    if files:
        response = gh('release', 'upload', tag, '--repo', repository, *files)
        if response.returncode:
            raise RuntimeError(response.stderr)
    print(f'Firmware verified on {release["html_url"]}: {name}')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(f'Firmware **{metadata["firmware_version"]}** available on [{tag}]({release["html_url"]}).\n\nSHA256: `{metadata["sha256"]}`\n')


if __name__ == '__main__':
    publish()
