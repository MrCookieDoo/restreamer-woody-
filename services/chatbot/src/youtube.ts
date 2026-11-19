import { OAuth2Client } from 'google-auth-library';
import type { Credentials } from 'google-auth-library';
import { youtube_v3 } from 'googleapis/build/src/apis/youtube/v3.js';
import { dispatch, readToken, saveToken, StudioApi, youtubeRole } from './common.ts';
import type { Config } from './common.ts';

export class YouTubeAdapter {
  private client: youtube_v3.Youtube | null = null;
  private chatId = '';
  private pageToken: string | undefined;
  private connectedAt = 0;
  private nextPoll = 0;
  private nextDiscovery = 0;
  private channel = '';
  constructor(private api: StudioApi, private tokenPath = '/data/youtube.json') {}

  async sync(config: Config) {
    if (!config.enabled || !config.youtube_channel) {
      this.stop();
      await this.api.status('youtube', 'disabled');
      return;
    }
    if (config.youtube_channel !== this.channel) { this.stop(); this.channel = config.youtube_channel; }
    if (Date.now() < this.nextPoll) return;
    try {
      if (!this.client) {
        const tokens = await readToken<Credentials>(this.tokenPath);
        if (!tokens || !process.env.YOUTUBE_CLIENT_ID || !process.env.YOUTUBE_CLIENT_SECRET) {
          this.nextPoll = Date.now() + 30000;
          await this.api.status('youtube', 'waiting', 'account-not-linked');
          return;
        }
        const auth = new OAuth2Client(process.env.YOUTUBE_CLIENT_ID, process.env.YOUTUBE_CLIENT_SECRET);
        auth.setCredentials(tokens);
        auth.on('tokens', updated => {
          Object.assign(tokens, updated);
          saveToken(this.tokenPath, tokens).catch(() => this.api.status('youtube', 'error', 'token-save-failed').catch(() => {}));
        });
        this.client = new youtube_v3.Youtube({ auth });
      }
      if (!this.chatId) {
        if (Date.now() < this.nextDiscovery) return;
        this.nextDiscovery = Date.now() + 60000;
        const active = await this.client.liveBroadcasts.list({ part: ['snippet'], mine: true, broadcastStatus: 'active', maxResults: 50 });
        const broadcast = active.data.items?.find(item => item.snippet?.channelId === config.youtube_channel);
        this.chatId = broadcast?.snippet?.liveChatId || '';
        if (!this.chatId) { await this.api.status('youtube', 'waiting', 'no-active-livechat'); return; }
        this.connectedAt = Date.now();
        this.pageToken = undefined;
      }
      const response = await this.client.liveChatMessages.list({ liveChatId: this.chatId, part: ['snippet', 'authorDetails'], pageToken: this.pageToken, maxResults: 200 });
      this.pageToken = response.data.nextPageToken || undefined;
      this.nextPoll = Date.now() + Math.max(1000, response.data.pollingIntervalMillis || 5000);
      for (const item of response.data.items || []) {
        const text = item.snippet?.textMessageDetails?.messageText;
        if (!text || !item.id || !item.authorDetails?.channelId) continue;
        const result = await dispatch(this.api, {
          platform: 'youtube', message_id: item.id, user_id: item.authorDetails.channelId,
          role: youtubeRole(item.authorDetails), text, timestamp: Date.parse(item.snippet?.publishedAt || '') / 1000,
        }, this.connectedAt);
        if (result?.accepted && !result.simulated) {
          await this.client.liveChatMessages.insert({ part: ['snippet'], requestBody: { snippet: { liveChatId: this.chatId, type: 'textMessageEvent', textMessageDetails: { messageText: result.reply.slice(0, 190) } } } });
        }
      }
      await this.api.status('youtube', 'connected');
    } catch (error) {
      const reason = (error as { response?: { data?: { error?: { errors?: { reason?: string }[] } } } }).response?.data?.error?.errors?.[0]?.reason;
      const quota = reason === 'quotaExceeded' || reason === 'dailyLimitExceeded';
      if (reason === 'liveChatEnded' || reason === 'liveChatDisabled') { this.chatId = ''; this.pageToken = undefined; }
      this.nextPoll = Date.now() + (quota ? 600000 : 60000);
      await this.api.status('youtube', 'error', quota ? 'quota-exceeded' : 'livechat-unavailable');
    }
  }

  stop() {
    this.client = null;
    this.chatId = '';
    this.pageToken = undefined;
    this.nextPoll = this.nextDiscovery = 0;
  }
}
