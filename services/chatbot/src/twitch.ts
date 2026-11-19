import { RefreshingAuthProvider } from '@twurple/auth';
import type { AccessToken } from '@twurple/auth';
import { ChatClient } from '@twurple/chat';
import { dispatch, readToken, saveToken, StudioApi, twitchRole } from './common.ts';
import type { Config } from './common.ts';

export class TwitchAdapter {
  private chat: ChatClient | null = null;
  private channel = '';
  private connectedAt = 0;
  private connected = false;
  constructor(private api: StudioApi, private tokenPath = '/data/twitch.json') {}

  async sync(config: Config) {
    if (!config.enabled || !config.twitch_channel) {
      this.stop();
      await this.api.status('twitch', 'disabled');
      return;
    }
    if (this.chat && this.channel === config.twitch_channel) {
      await this.api.status('twitch', this.connected ? 'connected' : 'waiting');
      return;
    }
    this.stop();
    const clientId = process.env.TWITCH_CLIENT_ID;
    const clientSecret = process.env.TWITCH_CLIENT_SECRET;
    const tokens = await readToken<AccessToken>(this.tokenPath);
    if (!clientId || !clientSecret || !tokens) {
      await this.api.status('twitch', 'waiting', 'account-not-linked');
      return;
    }
    const provider = new RefreshingAuthProvider({ clientId, clientSecret });
    provider.onRefresh(async (_id, token) => { await saveToken(this.tokenPath, token); });
    await provider.addUserForToken(tokens, ['chat']);
    this.channel = config.twitch_channel;
    this.chat = new ChatClient({ authProvider: provider, channels: [this.channel], logger: { minLevel: 'error' } });
    this.chat.onConnect(() => { this.connectedAt = Date.now(); this.connected = true; });
    this.chat.onDisconnect(() => { this.connected = false; });
    this.chat.onAuthenticationFailure(() => { this.connected = false; });
    this.chat.onMessage(async (channel, _user, text, message) => {
      if (channel.replace(/^#/, '').toLowerCase() !== this.channel) return;
      try {
        const timestamp = Number(message.tags.get('tmi-sent-ts'));
        const result = await dispatch(this.api, {
          platform: 'twitch', message_id: message.id, user_id: message.userInfo.userId,
          role: twitchRole(message.userInfo), text, timestamp: timestamp / 1000,
        }, this.connectedAt);
        if (result?.accepted && !result.simulated) await this.chat?.say(this.channel, result.reply.slice(0, 450));
      } catch { await this.api.status('twitch', 'error', 'message-failed').catch(() => {}); }
    });
    await this.chat.connect();
    await this.api.status('twitch', 'waiting', 'connecting');
  }

  stop() {
    this.chat?.quit();
    this.chat = null;
    this.channel = '';
    this.connected = false;
  }
}
