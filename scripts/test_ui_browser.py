#!/usr/bin/env python3
"""Exercise the real Studio bundle on a separate, already seeded demo installation.

Requires `pip install playwright` and `playwright install chromium`.
Never run against camera installations: only synthetic demo camera IDs are accepted.
"""
import argparse
import json
from pathlib import Path
import re
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8082')
parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
parser.add_argument('--chromium', help='Optional path to an installed Chromium executable')
args = parser.parse_args()
base = args.url.rstrip('/')
env = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines() if line and not line.startswith('#') and '=' in line)

def api(path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(base + path, headers=headers, data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

login = api('/api/login', {'username': env.get('CORE_API_AUTH_USERNAME', 'admin'), 'password': env['CORE_API_AUTH_PASSWORD']})
state = api('/api/woody/v1/state', token=login['access_token'])
if not state['cameras'] or any(not cid.startswith('00000000-0000-0000-0000-') for cid in state['cameras']):
    raise SystemExit('Use an isolated demo installation seeded with scripts/demo.py. Real camera installations are refused.')
artifacts = ROOT / 'artifacts' / 'studio-browser'
artifacts.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('localStorage.setItem("@@restreamer-ui@@token",' + json.dumps(login['refresh_token']) + ');localStorage.setItem("@@restreamer-ui@@updates","false")')
    try:
        page.goto(base + '/ui/#/studio')
        title = page.get_by_role('heading', name='Studio', exact=True)
        expect(title).to_be_visible(timeout=20000)
        # The actual VideoJS player must remain inside its own preview.
        preview = page.get_by_test_id('program-preview').bounding_box()
        player = page.locator('[data-vjs-player]').bounding_box()
        assert preview['width'] > 0 and preview['height'] > 0
        assert abs(preview['x'] - player['x']) < 2 and abs(preview['width'] - player['width']) < 2, (preview, player)
        for label in ['Volledig scherm', '1 groot + 5 klein', 'Alles naar wachtbeeld', '1 groot + 5 klein', 'Vastzetten', 'Vrijgeven']:
            page.get_by_role('button', name=label, exact=True).click(timeout=5000)
            expect(title).to_be_visible()
        page.get_by_role('button', name='Groot zetten', exact=True).first.click()
        page.get_by_role('button', name='Verbergen + dempen', exact=True).first.click()
        expect(page.get_by_text('Verborgen', exact=True)).to_be_visible()
        page.get_by_role('button', name='Vrijgeven', exact=True).click()
        page.get_by_role('button', name='Bewerk', exact=True).first.click()
        camera_dialog = page.get_by_role('dialog', name='Camera bewerken')
        expect(camera_dialog).to_be_visible()
        camera_dialog.get_by_role('button', name='Opslaan', exact=True).click()
        expect(camera_dialog).not_to_be_visible()
        page.get_by_role('button', name='Scène samenstellen', exact=True).click()
        dialog = page.get_by_role('dialog', name='Scène samenstellen')
        expect(dialog).to_be_visible()
        bounds = dialog.bounding_box()
        assert 0 <= bounds['x'] and bounds['x'] + bounds['width'] <= 1920
        dialog.get_by_label('Naam', exact=True).fill('Browserproef')
        dialog.get_by_label('Chatalias', exact=True).fill('browser-proef')
        dialog.get_by_role('button', name='Opslaan', exact=True).click()
        expect(dialog).not_to_be_visible()
        scene_button = page.get_by_role('button', name='Browserproef', exact=True)
        scene_button.click()
        scene_button.locator('..').get_by_role('button', name='Wis', exact=True).click()
        expect(scene_button).not_to_be_visible()
        # Backward compatibility: old Studio versions returned incomplete states.
        def partial(route):
            response = route.fetch()
            data = response.json()
            data.pop('engine', None)
            data.pop('program_channel_id', None)
            route.fulfill(response=response, json=data)
        page.route('**/api/woody/v1/program', partial)
        page.get_by_role('button', name='Alles naar wachtbeeld', exact=True).click()
        expect(page.get_by_text('Algemeen wachtbeeld actief. Chatbediening is vergrendeld.')).to_be_visible()
        expect(page.get_by_text(re.compile('^Mixer: '))).to_be_visible()
        page.unroute('**/api/woody/v1/program', partial)
        page.get_by_role('button', name='1 groot + 5 klein', exact=True).click()
        def reject(route):
            route.fulfill(status=409, json={'detail': 'Browserproef: opdracht geweigerd'})
        page.route('**/api/woody/v1/program', reject)
        page.get_by_role('button', name='Volledig scherm', exact=True).click()
        expect(page.get_by_text('Browserproef: opdracht geweigerd')).to_be_visible()
        expect(title).to_be_visible()
        page.unroute('**/api/woody/v1/program', reject)
        page.get_by_role('button', name='1 groot + 5 klein', exact=True).click()
        page.get_by_role('button', name='Preview vernieuwen', exact=True).click()
        page.screenshot(path=str(artifacts / 'desktop.png'), full_page=True)
        page.get_by_role('link', name='Chatbot', exact=True).click()
        expect(page.get_by_role('heading', name='Chatbot', exact=True)).to_be_visible()
        page.get_by_role('button', name='Commando simuleren', exact=True).click()
        expect(page.get_by_role('heading', name='Chatbot', exact=True)).to_be_visible()
        page.get_by_role('link', name='Naar Studio', exact=True).click()
        expect(title).to_be_visible()
        page.get_by_role('link', name='Naar Restreamer', exact=True).click()
        expect(page.get_by_role('link', name='Studio openen', exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('link', name='Studio openen', exact=True).click()
        expect(title).to_be_visible()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.get_by_role('button', name='1 groot + 5 klein', exact=True).click()
        assert page.evaluate('document.body.scrollWidth <= innerWidth'), 'Horizontal overflow on mobile'
        page.screenshot(path=str(artifacts / 'mobile.png'), full_page=True)
        assert not errors, errors
    except Exception:
        page.screenshot(path=str(artifacts / 'failure.png'), full_page=True)
        raise
    finally:
        browser.close()
print('Studio browser smoke passed: real player, buttons, modal, old responses, navigation and mobile layout.')
