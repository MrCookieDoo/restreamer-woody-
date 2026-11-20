import React from 'react';
import { act, render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import Player from '../../misc/Player';
import ProgramPreview from './ProgramPreview';

jest.mock('../../misc/Player', () => jest.fn(() => <div>Livevideo</div>));

const playlist = () => Promise.resolve({ ok: true, status: 200, text: async () => '#EXTM3U\n#EXTINF:2,\nframe.ts' });
const flush = async () => act(async () => {});
const advance = async (milliseconds) => act(async () => jest.advanceTimersByTime(milliseconds));
const originalFetch = global.fetch;

beforeEach(() => {
	jest.useFakeTimers();
	Player.mockClear();
	Player.mockImplementation(() => <div>Livevideo</div>);
	global.fetch = jest.fn();
});
afterEach(() => {
	cleanup();
	jest.clearAllTimers();
	jest.useRealTimers();
	global.fetch = originalFetch;
});

test('waits for a playable playlist and recovers automatically from an initial 404', async () => {
	fetch.mockResolvedValueOnce({ ok: false, status: 404 }).mockImplementation(playlist);
	render(<ProgramPreview source="/memfs/program.m3u8" />);
	await flush();
	expect(screen.getByRole('status')).toHaveTextContent('Wacht op de hoofdstream');
	expect(Player).not.toHaveBeenCalled();
	await advance(3000);
	expect(screen.getByText('Livevideo')).toBeInTheDocument();
	expect(fetch).toHaveBeenCalledTimes(2);
});

test('does not start a player for HTML or an empty media playlist returned with HTTP 200', async () => {
	fetch.mockResolvedValueOnce({ ok: true, status: 200, text: async () => '<html>Unavailable</html>' })
		.mockResolvedValueOnce({ ok: true, status: 200, text: async () => '#EXTM3U\n#EXT-X-TARGETDURATION:2' })
		.mockImplementation(playlist);
	render(<ProgramPreview source="/memfs/program.m3u8" />);
	await flush();
	expect(Player).not.toHaveBeenCalled();
	await advance(3000);
	expect(Player).not.toHaveBeenCalled();
	await advance(3000);
	expect(screen.getByText('Livevideo')).toBeInTheDocument();
});

function player() {
	const handlers = {};
	return { handlers, on: (name, callback) => { handlers[name] = callback; }, off: jest.fn(),
		currentTime: jest.fn(() => 1), paused: jest.fn(() => false), isDisposed: jest.fn(() => false) };
}

async function mountWithPlayer() {
	fetch.mockImplementation(playlist);
	const view = render(<ProgramPreview source="/memfs/program.m3u8" />);
	await flush();
	const video = player();
	act(() => Player.mock.calls[Player.mock.calls.length - 1][0].onReady(video));
	return { video, view };
}

test('reconnects after a player error with a delay instead of a tight retry loop', async () => {
	const { video } = await mountWithPlayer();
	act(() => video.handlers.error());
	expect(screen.queryByText('Livevideo')).not.toBeInTheDocument();
	expect(fetch).toHaveBeenCalledTimes(1);
	await advance(3000);
	expect(fetch).toHaveBeenCalledTimes(2);
	expect(screen.getByText('Livevideo')).toBeInTheDocument();
});

test('recovers a player whose playback clock has stopped', async () => {
	await mountWithPlayer();
	await advance(16000);
	expect(screen.getByRole('status')).toHaveTextContent('opnieuw verbonden');
	await advance(3000);
	expect(fetch).toHaveBeenCalledTimes(2);
});

test('leaves a deliberately paused player alone', async () => {
	const { video } = await mountWithPlayer();
	video.paused.mockReturnValue(true);
	await advance(20000);
	expect(fetch).toHaveBeenCalledTimes(1);
	expect(screen.getByText('Livevideo')).toBeInTheDocument();
});

test('aborts an outstanding availability request when leaving Studio', async () => {
	fetch.mockImplementation(() => new Promise(() => {}));
	const view = render(<ProgramPreview source="/memfs/program.m3u8" />);
	const signal = fetch.mock.calls[0][1].signal;
	view.unmount();
	expect(signal.aborted).toBe(true);
});
