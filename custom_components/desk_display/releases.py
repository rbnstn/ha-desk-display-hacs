"""One cached, bounded release lookup for UI and native update entities."""
import json
import re
from pathlib import Path
from time import monotonic
import aiohttp


async def latest_release(hass):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    cached=hass.data.get('desk_display_release_cache')
    if cached and monotonic()-cached[0]<900:return cached[1]
    async with async_get_clientsession(hass).get('https://api.github.com/repos/rbnstn/ha-desk-display-hacs/releases/latest',timeout=aiohttp.ClientTimeout(total=10)) as response:
        response.raise_for_status();release=await response.json()
    installed=await hass.async_add_executor_job(lambda:json.loads(Path(__file__).with_name('manifest.json').read_text())['version'])
    result={'installed':installed,'latest':release['tag_name'].removeprefix('v'),'title':release['name'],'url':release['html_url']}
    for asset in release.get('assets',[]):
        version=re.fullmatch(r'desk-display-e32r35t-([0-9]+\.[0-9]+\.[0-9]+)\.bin',asset['name'])
        if version:
            url=asset['browser_download_url']
            if not url.startswith('https://github.com/rbnstn/ha-desk-display-hacs/releases/download/'):raise ValueError('Unexpected firmware URL')
            result.update(firmware=version[1],firmware_url=url)
    hass.data['desk_display_release_cache']=(monotonic(),result)
    return result
