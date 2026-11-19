import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../../theme';
import Studio, { CameraBoard } from './Studio';
import Chatbot from './Chatbot';

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
