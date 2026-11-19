import assert from 'node:assert/strict';
import test from 'node:test';
import { dispatch, eligible, twitchRole, youtubeRole } from '../src/common.ts';

test('roles derive from provider flags, including owner precedence', () => {
  assert.equal(twitchRole({ isBroadcaster: false, isMod: false }), 'viewer');
  assert.equal(twitchRole({ isBroadcaster: false, isMod: true }), 'moderator');
  assert.equal(twitchRole({ isBroadcaster: true, isMod: true }), 'owner');
  assert.equal(youtubeRole({}), 'viewer');
  assert.equal(youtubeRole({ isChatModerator: true }), 'moderator');
  assert.equal(youtubeRole({ isChatOwner: true, isChatModerator: true }), 'owner');
});

test('old chat history, unrelated commands and invalid timestamps are ignored', () => {
  assert.equal(eligible('!camera garden', 100000, 99000, 101000), true);
  assert.equal(eligible('!camera garden', 100000, 101000, 101000), false);
  assert.equal(eligible('!camera garden', 100000, 99000, 140000), false);
  assert.equal(eligible('!camerafoo garden', 100000, 99000, 101000), false);
  assert.equal(eligible('hello', 100000, 99000, 101000), false);
  assert.equal(eligible('!scenes', NaN, 0), false);
});

test('both platforms send normalized commands through the same Studio authority', async () => {
  const now = Date.now();
  const calls: unknown[] = [];
  const api = { command: async (event: unknown) => { calls.push(event); return { accepted: true, simulated: false, reply: 'ok' }; } };
  for (const platform of ['twitch', 'youtube'] as const) {
    const event = { platform, message_id: 'provider-id', user_id: 'stable-user-id', role: 'moderator' as const, text: '!scene garden', timestamp: now / 1000 };
    assert.equal((await dispatch(api, event, now - 1000))?.accepted, true);
    assert.equal(await dispatch(api, { ...event, timestamp: (now - 60000) / 1000 }, now - 1000), null);
  }
  assert.equal(calls.length, 2);
});
