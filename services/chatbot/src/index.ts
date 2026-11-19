import { StudioApi } from './common.ts';
import { TwitchAdapter } from './twitch.ts';
import { YouTubeAdapter } from './youtube.ts';

const api = new StudioApi();
const twitch = new TwitchAdapter(api);
const youtube = new YouTubeAdapter(api);
let stopping = false;
const retryAt = [0, 0];
const attempts = [0, 0];
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => { stopping = true; twitch.stop(); youtube.stop(); });

while (!stopping) {
  try {
    const config = await api.config();
    // Each adapter failure is isolated; Studio and the stream keep running.
    const adapters = [twitch, youtube];
    const results = await Promise.allSettled(adapters.map((adapter, index) => Date.now() >= retryAt[index] ? adapter.sync(config) : Promise.resolve()));
    for (let i = 0; i < results.length; i++) {
      if (results[i].status === 'rejected') {
        attempts[i] += 1;
        retryAt[i] = Date.now() + Math.min(60000, 5000 * 2 ** Math.min(attempts[i], 4));
        await api.status(i === 0 ? 'twitch' : 'youtube', 'error', 'connection-failed').catch(() => {});
      } else if (Date.now() >= retryAt[i]) {
        attempts[i] = 0;
      }
    }
  } catch { console.error('Studio unavailable; retrying.'); }
  if (!stopping) await new Promise(resolve => setTimeout(resolve, 1000));
}
