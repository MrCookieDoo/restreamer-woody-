/** Local OAuth handoff. No credentials are requested through chat or stored in Git. */
import { createServer } from 'node:http';
import { randomBytes } from 'node:crypto';
import { OAuth2Client } from 'google-auth-library';
import { getTokenInfo } from '@twurple/auth';
import { saveToken } from './common.ts';

const platform = process.argv[2];
if (platform !== 'twitch' && platform !== 'youtube') throw new Error('Usage: npm run link -- twitch|youtube');
const redirect = 'http://localhost:8787/callback';
const nonce = randomBytes(32).toString('hex');
const prefix = platform.toUpperCase();
const id = process.env[`${prefix}_CLIENT_ID`];
const secret = process.env[`${prefix}_CLIENT_SECRET`];
if (!id || !secret) throw new Error(`Set ${prefix}_CLIENT_ID and ${prefix}_CLIENT_SECRET`);
const google = new OAuth2Client(id, secret, redirect);
const url = platform === 'youtube'
  ? google.generateAuthUrl({ access_type: 'offline', prompt: 'consent', scope: ['https://www.googleapis.com/auth/youtube.force-ssl'], state: nonce })
  : 'https://id.twitch.tv/oauth2/authorize?' + new URLSearchParams({ client_id: id, redirect_uri: redirect, response_type: 'code', scope: 'chat:read chat:edit', state: nonce });
let used = false;
const server = createServer(async (request, response) => {
  const callback = new URL(request.url || '/', redirect);
  if (callback.pathname !== '/callback' || callback.searchParams.get('state') !== nonce || used) { response.writeHead(400).end('Invalid callback'); return; }
  const code = callback.searchParams.get('code');
  if (!code) { response.writeHead(400).end('Authorization was not completed'); return; }
  used = true;
  try {
    let token;
    if (platform === 'youtube') {
      token = (await google.getToken(code)).tokens;
    } else {
      const result = await fetch('https://id.twitch.tv/oauth2/token', { method: 'POST', body: new URLSearchParams({ client_id: id, client_secret: secret, code, grant_type: 'authorization_code', redirect_uri: redirect }) });
      if (!result.ok) throw new Error('Authorization failed');
      const data = await result.json() as { access_token: string; refresh_token: string; expires_in: number; scope: string[] };
      await getTokenInfo(data.access_token, id);
      token = { accessToken: data.access_token, refreshToken: data.refresh_token, expiresIn: data.expires_in, obtainmentTimestamp: Date.now(), scope: data.scope };
    }
    await saveToken(`${process.env.WOODY_TOKEN_DIR || '/data'}/${platform}.json`, token);
    response.end('Account linked. You may close this window.');
  } catch { response.writeHead(500).end('Account could not be linked. Check the app configuration.'); }
  finally { server.close(); }
});
server.listen(8787, '0.0.0.0', () => console.log(`Open this URL in your browser:\n${url}`));
setTimeout(() => { server.close(); process.exitCode = 1; }, 300000).unref();
