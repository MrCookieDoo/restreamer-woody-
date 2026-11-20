import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../../theme';
import Studio, { CameraBoard } from './Studio';
import Chatbot from './Chatbot';
import StudioBoundary from './StudioBoundary';
import StudioLink from '../../misc/StudioLink';

jest.mock('../../misc/Player', () => () => <div>Programmapreview</div>);

const camera = { channel_id: 'garden-id', name: 'Tuin', alias: 'tuin', state: 'online', audio: true, hidden: false, chat_enabled: true };
function state() {
	return {
		cameras: { 'garden-id': camera },
		scenes: {},
		bots: {},
		program: { safe: false, pinned: false, layout: 'six', slots: ['garden-id'], next_switch_in: 180, border_color: '#85532d', border_width: 4 },
		rotation: { enabled: true, interval_seconds: 180, order: ['garden-id'] },
		chat: { enabled: false, dry_run: true, viewer_enabled: false, global_cooldown: 10, user_cooldown: 30, twitch_channel: '', youtube_channel: '' },
		engine: { state: 'running' },
		program_channel_id: 'program-id',
	};
}
function restreamer(current = state()) {
	return {
		GetChannelAddress: jest.fn(() => '/snapshot.jpg'),
		StudioRequest: jest.fn(async (method, path) => (path === '/channels' ? [] : current)),
	};
}
const wrap = (view) => render(<ThemeProvider theme={theme}>{view}</ThemeProvider>);

test('hidden camera produces no snapshot or selectable camera on the control board', () => {
	const rs = restreamer();
	wrap(<CameraBoard slots={['garden-id']} cameras={{ 'garden-id': { ...camera, hidden: true } }} restreamer={rs} />);
	expect(screen.queryByRole('img')).not.toBeInTheDocument();
	expect(screen.getByRole('button', { name: 'Wachtbeeld kader 1' })).toBeDisabled();
	expect(rs.GetChannelAddress).not.toHaveBeenCalled();
});

test('camera emergency button sends the hide command rather than stopping the Core channel', async () => {
	const rs = restreamer();
	wrap(<Studio restreamer={rs} />);
	await screen.findByRole('button', { name: 'Verbergen + dempen' });
	fireEvent.click(screen.getByRole('button', { name: 'Verbergen + dempen' }));
	await waitFor(() => expect(rs.StudioRequest).toHaveBeenCalledWith('PUT', '/cameras/garden-id/hidden', { hidden: true }));
});

test('chat simulator explicitly marks the request as a simulation', async () => {
	const rs = restreamer();
	wrap(<Chatbot restreamer={rs} />);
	await screen.findByRole('button', { name: 'Commando simuleren' });
	fireEvent.click(screen.getByRole('button', { name: 'Commando simuleren' }));
	await waitFor(() =>
		expect(rs.StudioRequest).toHaveBeenCalledWith(
			'POST',
			'/chat/simulate',
			expect.objectContaining({ simulate: true, platform: 'simulator', role: 'moderator' }),
		),
	);
});

test('button responses from an older Studio server preserve the engine and preview until polling completes', async () => {
	const current = state();
	const rs = restreamer(current);
	let loaded = false;
	rs.StudioRequest.mockImplementation((method, path) => {
		if (path === '/channels') return Promise.resolve([]);
		if (method === 'GET') {
			if (loaded) return new Promise(() => {}); // Poll is still in flight.
			loaded = true;
			return Promise.resolve(current);
		}
		const { engine, program_channel_id, ...partial } = current;
		return Promise.resolve({ ...partial, revision: 2, program: { ...current.program, safe: true } });
	});
	wrap(<Studio restreamer={rs} />);
	fireEvent.click(await screen.findByRole('button', { name: 'Alles naar wachtbeeld' }));
	await screen.findByText('Algemeen wachtbeeld actief. Chatbediening is vergrendeld.');
	expect(screen.getByText('Mixer: running')).toBeInTheDocument();
	expect(screen.getByText('Programmapreview')).toBeInTheDocument();
	expect(screen.getByRole('button', { name: '1 groot + 5 klein' })).toBeInTheDocument();
});

test('the Restreamer home page entry links directly to Studio', () => {
	wrap(<StudioLink />);
	expect(screen.getByRole('link', { name: 'Studio openen' })).toHaveAttribute('href', '#/studio');
});

test('a Studio render error presents recovery controls instead of a blank page', () => {
	const log = jest.spyOn(console, 'error').mockImplementation(() => {});
	function BrokenStudio() {
		throw new Error('Test render failure');
	}
	wrap(
		<StudioBoundary>
			<BrokenStudio />
		</StudioBoundary>,
	);
	expect(screen.getByRole('alert')).toHaveTextContent('Studio kon niet worden weergegeven');
	expect(screen.getByRole('link', { name: 'Naar Restreamer' })).toHaveAttribute('href', '#/');
	expect(screen.getByRole('button', { name: 'Studio opnieuw laden' })).toBeEnabled();
	log.mockRestore();
});
