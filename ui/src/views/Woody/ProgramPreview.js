import React from 'react';
import { Box, CircularProgress, Stack, Typography } from '@mui/material';
import Player from '../../misc/Player';

export default function ProgramPreview({ source }) {
	const [ready, setReady] = React.useState(false);
	const [message, setMessage] = React.useState('Hoofdstream wordt geladen…');
	const [retry, setRetry] = React.useState(0);
	const [player, setPlayer] = React.useState(null);
	React.useEffect(() => {
		let stopped = false;
		let timer;
		const abort = new AbortController();
		setReady(false);
		const check = async () => {
			const timeout = setTimeout(() => abort.abort(), 8000);
			try {
				const response = await fetch(source, { cache: 'no-store', signal: abort.signal });
				const body = response.ok ? await response.text() : '';
				if (stopped) return;
				if (body.trimStart().startsWith('#EXTM3U') && /#EXTINF:|#EXT-X-STREAM-INF:/.test(body)) {
					setReady(true);
					return;
				}
				setMessage(response.status === 404 ? 'Wacht op de hoofdstream. Maak het hoofdkanaal gereed als dit nog niet is gedaan.' : 'Wacht op een afspeelbare hoofdstream…');
			} catch {
				if (!stopped) setMessage('Hoofdstream tijdelijk niet bereikbaar. De preview probeert opnieuw.');
			} finally {
				clearTimeout(timeout);
			}
			if (!stopped) timer = setTimeout(() => setRetry((value) => value + 1), 3000);
		};
		check();
		return () => {
			stopped = true;
			abort.abort();
			clearTimeout(timer);
		};
	}, [source, retry]);
	React.useEffect(() => {
		if (!player) return;
		let recovering = false;
		let recoveryTimer;
		let lastTime = player.currentTime();
		let lastProgress = Date.now();
		const recover = () => {
			if (recovering || player.isDisposed()) return;
			recovering = true;
			setMessage('De preview wordt opnieuw verbonden…');
			setReady(false);
			recoveryTimer = setTimeout(() => setRetry((value) => value + 1), 3000);
		};
		player.on('error', recover);
		const timer = setInterval(() => {
			if (player.isDisposed()) return;
			const current = player.currentTime();
			if (player.paused() || current !== lastTime) lastProgress = Date.now();
			lastTime = current;
			if (Date.now() - lastProgress > 15000) recover();
		}, 2000);
		return () => {
			clearInterval(timer);
			clearTimeout(recoveryTimer);
			if (!player.isDisposed()) player.off('error', recover);
		};
	}, [player]);
	return ready ? (
		<Player key={`${source}:${retry}`} source={source} controls autoplay onReady={setPlayer} />
	) : (
		<Box role="status" sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', p: 3 }}>
			<Stack spacing={2} alignItems="center">
				<CircularProgress size={28} />
				<Typography align="center">{message}</Typography>
			</Stack>
		</Box>
	);
}
