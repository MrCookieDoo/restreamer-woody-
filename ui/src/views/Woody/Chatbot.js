import React from 'react';
import { v4 as uuidv4 } from 'uuid';
import {
	Alert,
	Box,
	Button,
	Card,
	CardContent,
	Chip,
	CircularProgress,
	FormControlLabel,
	Grid,
	MenuItem,
	Stack,
	Switch,
	TextField,
	Typography,
} from '@mui/material';
import useStudio from './useStudio';

export default function Chatbot({ restreamer }) {
	const { state, error, busy, request } = useStudio(restreamer);
	const [form, setForm] = React.useState(null);
	const [text, setText] = React.useState('!camera tuin');
	const [role, setRole] = React.useState('moderator');
	const [result, setResult] = React.useState(null);
	const [audit, setAudit] = React.useState([]);
	const [notice, setNotice] = React.useState('');
	React.useEffect(() => {
		if (!form && state?.chat) setForm({ ...state.chat });
	}, [form, state]);
	if (!state || !form) return <Box sx={{ p: 4 }}>{error ? <Alert severity="error">{error}</Alert> : <CircularProgress />}</Box>;
	const change = (key, value) => setForm({ ...form, [key]: value });
	const simulate = async () =>
		setResult(
			await request('POST', '/chat/simulate', {
				platform: 'simulator',
				message_id: uuidv4(),
				user_id: 'local-test',
				role,
				text,
				timestamp: Date.now() / 1000,
				simulate: true,
			}),
		);
	return (
		<Box sx={{ px: { xs: 2, md: 5 }, pb: 8 }}>
			<Stack direction="row" justifyContent="space-between" mb={3}>
				<Box>
					<Typography variant="h4">Chatbot</Typography>
					<Typography color="text.secondary">Twitch en YouTube · bediening voor moderators en kanaaleigenaar</Typography>
				</Box>
				<Button href="#/studio">Naar regie</Button>
			</Stack>
			{error && (
				<Alert severity="error" sx={{ mb: 2 }}>
					{error}
				</Alert>
			)}
			{notice && (
				<Alert severity="success" sx={{ mb: 2 }}>
					{notice}
				</Alert>
			)}
			{(state.program.safe || state.program.pinned) && (
				<Alert severity="warning" sx={{ mb: 2 }}>
					De regie is vergrendeld. Chat kan het beeld niet wijzigen.
				</Alert>
			)}
			<Grid container spacing={3}>
				<Grid item xs={12} md={6}>
					<Card>
						<CardContent>
							<Typography variant="h6" mb={2}>
								Instellingen
							</Typography>
							<Stack spacing={2}>
								<FormControlLabel
									label="Chatbediening inschakelen"
									control={<Switch checked={form.enabled} onChange={(e) => change('enabled', e.target.checked)} />}
								/>
								<FormControlLabel
									label="Simulatiemodus — echte chat wijzigt geen beeld"
									control={<Switch checked={form.dry_run} onChange={(e) => change('dry_run', e.target.checked)} />}
								/>
								{!form.dry_run && <Alert severity="info">Toegestane chatcommando’s kunnen na opslaan de hoofdstream wijzigen.</Alert>}
								<TextField
									label="Twitch-kanaalnaam"
									value={form.twitch_channel}
									onChange={(e) => change('twitch_channel', e.target.value.toLowerCase())}
								/>
								<TextField
									label="YouTube-kanaal-ID"
									value={form.youtube_channel}
									onChange={(e) => change('youtube_channel', e.target.value)}
									helperText="Het gekoppelde YouTube-account moet de actieve livestream kunnen beheren."
								/>
								<Stack direction="row" spacing={2}>
									<TextField
										type="number"
										label="Wachttijd gezamenlijk (s)"
										value={form.global_cooldown}
										onChange={(e) => change('global_cooldown', Number(e.target.value))}
									/>
									<TextField
										type="number"
										label="Wachttijd per gebruiker (s)"
										value={form.user_cooldown}
										onChange={(e) => change('user_cooldown', Number(e.target.value))}
									/>
								</Stack>
								<Typography variant="body2">
									Kijkers kunnen beschikbare camera’s en scènes opvragen. Wisselen is voor moderators en de kanaaleigenaar. Camera’s en scènes
									geef je afzonderlijk vrij in Regie.
								</Typography>
								<Button
									variant="contained"
									disabled={busy}
									onClick={async () => {
										if (await request('PUT', '/chat', form)) setNotice('Chatbotinstellingen opgeslagen.');
									}}
								>
									Instellingen opslaan
								</Button>
							</Stack>
						</CardContent>
					</Card>
				</Grid>
				<Grid item xs={12} md={6}>
					<Card>
						<CardContent>
							<Typography variant="h6" mb={2}>
								Verbindingen
							</Typography>
							<Stack spacing={2}>
								{['twitch', 'youtube'].map((platform) => {
									const status = state.bots[platform];
									const fresh = status && Date.now() / 1000 - status.at < 90;
									return (
										<Stack direction="row" key={platform} justifyContent="space-between">
											<Typography sx={{ textTransform: 'capitalize' }}>{platform}</Typography>
											<Chip
												label={fresh ? status.state : 'Niet verbonden'}
												color={fresh && status.state === 'connected' ? 'success' : 'default'}
											/>
										</Stack>
									);
								})}
								<Typography variant="body2" color="text.secondary">
									Accountkoppeling gebeurt via de installatiehandleiding. Start de optionele chatbotservice nadat de accounts zijn gekoppeld.
								</Typography>
								<Button
									component="a"
									href="https://github.com/MrCookieDoo/restreamer-woody-/blob/feat/woody-studio/docs/CHATBOT.md"
									target="_blank"
									rel="noreferrer"
								>
									Handleiding accountkoppeling
								</Button>
							</Stack>
						</CardContent>
					</Card>
					<Card sx={{ mt: 3 }}>
						<CardContent>
							<Typography variant="h6" mb={2}>
								Lokaal testen
							</Typography>
							<Stack spacing={2}>
								<Typography variant="body2">Test dezelfde rechten en blokkeringen zonder de uitzending te wijzigen.</Typography>
								<TextField select label="Rol" value={role} onChange={(e) => setRole(e.target.value)}>
									{[
										['viewer', 'Kijker'],
										['moderator', 'Moderator'],
										['owner', 'Kanaaleigenaar'],
									].map(([value, name]) => (
										<MenuItem value={value} key={value}>
											{name}
										</MenuItem>
									))}
								</TextField>
								<TextField
									label="Commando"
									value={text}
									onChange={(e) => setText(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === 'Enter') simulate();
									}}
								/>
								<Button variant="outlined" disabled={busy || !text} onClick={simulate}>
									Commando simuleren
								</Button>
								{result && <Alert severity={result.accepted ? 'success' : 'warning'}>{result.reply}</Alert>}
								<Typography variant="caption">!cameras · !scenes · !camera &lt;alias&gt; · !scene &lt;alias&gt; · !auto on/off</Typography>
							</Stack>
						</CardContent>
					</Card>
				</Grid>
				<Grid item xs={12}>
					<Card>
						<CardContent>
							<Stack direction="row" justifyContent="space-between">
								<Typography variant="h6">Recente opdrachten</Typography>
								<Button
									disabled={busy}
									onClick={async () => {
										const entries = await request('GET', '/chat/audit');
										if (entries) setAudit(entries);
									}}
								>
									Vernieuwen
								</Button>
							</Stack>
							<Stack spacing={1} mt={2}>
								{audit.map((entry) => (
									<Box key={entry.id}>
										<Typography variant="body2">
											{new Date(entry.at * 1000).toLocaleTimeString()} · {entry.actor} · {entry.action}
										</Typography>
										<Typography variant="caption" color="text.secondary">
											{entry.outcome}
										</Typography>
									</Box>
								))}
							</Stack>
						</CardContent>
					</Card>
				</Grid>
			</Grid>
		</Box>
	);
}
