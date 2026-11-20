import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

export type Platform = 'twitch' | 'youtube';
export type Role = 'viewer' | 'moderator' | 'owner';
export type Config = { enabled: boolean; dry_run: boolean; twitch_channel: string; youtube_channel: string };
export type Message = { platform: Platform; message_id: string; user_id: string; role: Role; text: string; timestamp: number };
export type Result = { accepted: boolean; simulated: boolean; reply: string };

export class StudioApi {
  constructor(private base = process.env.WOODY_API || 'http://studio:8090/api/woody/v1', private token = process.env.WOODY_BOT_TOKEN || '') {
    if (token.length < 32) throw new Error('WOODY_BOT_TOKEN is required');
  }
  async call<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(this.base + '/bot' + path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${this.token}`, 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error('Studio request failed');
    return response.json() as Promise<T>;
  }
  config() { return this.call<Config>('/config'); }
  command(message: Message) { return this.call<Result>('/command', message); }
  async status(platform: Platform, state: 'disabled' | 'waiting' | 'connected' | 'error', detail = '') {
    await this.call('/status', { platform, state, detail });
  }
}

export async function readToken<T>(path: string): Promise<T | null> {
  try { return JSON.parse(await readFile(path, 'utf8')) as T; }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw new Error('Token file cannot be read');
  }
}

export async function saveToken(path: string, token: unknown) {
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await writeFile(path + '.tmp', JSON.stringify(token), { mode: 0o600 });
  await rename(path + '.tmp', path);
}

export function twitchRole(info: { isBroadcaster: boolean; isMod: boolean }): Role {
  return info.isBroadcaster ? 'owner' : info.isMod ? 'moderator' : 'viewer';
}
export function youtubeRole(info: { isChatOwner?: boolean | null; isChatModerator?: boolean | null }): Role {
  return info.isChatOwner ? 'owner' : info.isChatModerator ? 'moderator' : 'viewer';
}
export function eligible(text: string, timestamp: number, connectedAt: number, now = Date.now()): boolean {
  return /^!(cameras|scenes|camera|scene|auto)(\s|$)/i.test(text) && Number.isFinite(timestamp) && timestamp >= connectedAt && Math.abs(now - timestamp) <= 30000;
}

// Provider adapters only produce normalized events. Authorization lives in Studio.
export async function dispatch(api: Pick<StudioApi, 'command'>, event: Message, connectedAt: number): Promise<Result | null> {
  if (!eligible(event.text, event.timestamp * 1000, connectedAt)) return null;
  return api.command(event);
}
