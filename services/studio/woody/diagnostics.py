"""Read-only report; can also be piped into an older Studio container.

Only explicitly selected counters/status codes leave the container. Never emit
environment values, source addresses, API response bodies or exception messages.
"""
import json
import os
import time

PROGRAM_ID = 'dba994be-cac9-43f4-9d3f-72629c286640'


class Unavailable(Exception):
    def __init__(self, status=0):
        self.status = status


def number(value):
    return value if type(value) in (int, float) else None


def enum(value, choices):
    return value if value in choices else 'unknown'


def snapshot(request):
    report = {}
    try:
        state = request('studio', '/api/woody/v1/state')
        engine = state.get('engine', {})
        cameras = list(state.get('cameras', {}).values())
        report['studio'] = {
            'state': enum(engine.get('state'), ('starting', 'running', 'error', 'disabled')),
            'frames': number(engine.get('frames')), 'restarts': number(engine.get('restarts')),
            'cameras': len(cameras), 'online': sum(c.get('state') == 'online' for c in cameras),
            'with_audio': sum(c.get('audio') is True for c in cameras),
        }
        for key in ('output_frames', 'output_fps', 'output_age_seconds'):
            if number(engine.get(key)) is not None:
                report['studio'][key] = engine[key]
    except Unavailable as error:
        report['studio'] = {'http_status': error.status}
    try:
        process = request('core', '/api/v3/process/restreamer-ui:ingest:' + PROGRAM_ID + '?filter=state')
        state = process.get('state', {})
        progress = state.get('progress', {})
        report['program'] = {
            'exists': True,
            'exec': enum(state.get('exec'), ('starting', 'running', 'finishing', 'finished', 'killed', 'failed')),
            'order': enum(state.get('order'), ('start', 'stop')),
            'frames': number(progress.get('frame', progress.get('frames'))),
            'fps': number(progress.get('fps')), 'speed': number(progress.get('speed')),
        }
    except Unavailable as error:
        report['program'] = {'exists': False if error.status == 404 else None, 'http_status': error.status}
    try:
        playlist = request('core', '/memfs/' + PROGRAM_ID + '.m3u8', text=True)
        report['hls'] = {'http_status': 200, 'playlist': playlist.lstrip('\ufeff').startswith('#EXTM3U')}
    except Unavailable as error:
        report['hls'] = {'http_status': error.status, 'playlist': False}
    return report


def main():
    import httpx
    import jwt
    secret = os.getenv('CORE_API_AUTH_USERNAME', 'admin') + os.environ['CORE_API_AUTH_PASSWORD'] + os.environ['CORE_API_AUTH_JWT_SECRET']
    token = jwt.encode({'sub': 'woody-diagnostics', 'usefor': 'access', 'iat': int(time.time()), 'exp': int(time.time()) + 120}, secret, algorithm='HS256')
    addresses = {'studio': 'http://127.0.0.1:8090', 'core': os.getenv('WOODY_CORE_URL', 'http://core:8080').rstrip('/')}
    with httpx.Client(timeout=5, trust_env=False, headers={'Authorization': 'Bearer ' + token}) as client:
        def request(service, path, text=False):
            try:
                response = client.get(addresses[service] + path)
                if response.status_code != 200:
                    raise Unavailable(response.status_code)
                return response.text if text else response.json()
            except (httpx.HTTPError, ValueError):
                raise Unavailable() from None
        first = snapshot(request)
        time.sleep(3)
        second = snapshot(request)
    result = {'first': first, 'after_3_seconds': second}
    for key in ('studio', 'program'):
        a, b = first[key].get('frames'), second[key].get('frames')
        if a is not None and b is not None:
            result[key + '_frames_advanced'] = b > a
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Diagnostic failed; no private error details printed.')
        raise SystemExit(1)
