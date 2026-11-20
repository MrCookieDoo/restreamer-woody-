import React from 'react';
import {
	Alert,
	Box,
	Button,
	Card,
	CardContent,
	Chip,
	CircularProgress,
	Dialog,
	DialogActions,
	DialogContent,
	DialogTitle,
	FormControlLabel,
	Grid,
	MenuItem,
	Stack,
	Switch,
	TextField,
	Typography,
} from '@mui/material';
import VideocamIcon from '@mui/icons-material/Videocam';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ProgramPreview from './ProgramPreview';
import useStudio from './useStudio';
import useSlates from './useSlates';

// The upstream theme styles MuiDialog like an inline paper; restore the modal root locally.
const dialogLayout = { p: 0, width: 'auto', maxWidth: 'none', maxHeight: 'none', overflow: 'visible', bgcolor: 'transparent' };

const sourceReasons = {
	'waiting-for-frames': 'Verbinding wordt gemaakt; wacht op camerabeeld.',
	'connection-error': 'Studio kan de camerabron niet bereiken.',
	'authentication-error': 'De camerabron weigert de aanmelding.',
	'source-not-found': 'De camerabron is niet gevonden.',
	'format-error': 'Het beeldformaat kon niet worden verwerkt.',
	'decoder-missing': 'Een decoder voor deze camerabron ontbreekt.',
	'decode-error': 'De camerastream kon niet worden gedecodeerd.',
	'stream-ended': 'De camerabron heeft de verbinding beëindigd.',
	'pipeline-error': 'De camera-ontvangst kon niet worden gestart.',
};

const areas = ['2 / 2 / 4 / 4', '2 / 1 / 3 / 2', '3 / 1 / 4 / 2', '4 / 1 / 5 / 2', '4 / 2 / 5 / 3', '4 / 3 / 5 / 4'];

export function CameraBoard({ slots = [], cameras, slates = {}, restreamer, safe, full, onSwitch, disabled, color = '#85532d', border = 4 }) {
	return (
		<Box
			sx={{
				display: 'grid',
				gridTemplateColumns: 'repeat(3, 1fr)',
				gridTemplateRows: '0 repeat(3, 1fr)',
				aspectRatio: '16 / 9',
				background: color,
				gap: `${border}px`,
				p: `${border}px`,
				borderRadius: 1,
				overflow: 'hidden',
			}}
		>
			{(safe || full ? [0] : [0, 1, 2, 3, 4, 5]).map((i) => {
				const cid = safe ? null : slots[i];
				const camera = cameras[cid];
				const visible = camera && !camera.hidden && camera.state === 'online';
				const slate = !safe && !visible && slates[cid]?.image_data;
				return (
					<Box
						component="button"
						key={i}
						aria-label={visible ? `Maak ${camera.name} groot` : `Wachtbeeld kader ${i + 1}`}
						disabled={disabled || !visible || i === 0}
						onClick={() => onSwitch?.(cid)}
						sx={{
							gridArea: safe || full ? '2 / 1 / 5 / 4' : areas[i],
							position: 'relative',
							minWidth: 0,
							border: 0,
							p: 0,
							background: '#101412',
							color: 'white',
							overflow: 'hidden',
							cursor: i > 0 && visible ? 'pointer' : 'default',
							'&:focus-visible': { outline: '3px solid white', outlineOffset: -3 },
						}}
					>
						{visible && (
							<Box
								component="img"
								alt=""
								src={`${restreamer.GetChannelAddress('snapshot+memfs', cid)}?t=${Math.floor(Date.now() / 5000)}`}
								onError={(event) => {
									event.currentTarget.style.visibility = 'hidden';
								}}
								onLoad={(event) => {
									event.currentTarget.style.visibility = 'visible';
								}}
								sx={{ width: '100%', height: '100%', objectFit: 'contain' }}
							/>
						)}
						{slate && (
							<Box
								component="img"
								alt={`Eigen wachtbeeld voor ${camera.name}`}
								src={slate}
								sx={{ width: '100%', height: '100%', objectFit: 'contain' }}
							/>
						)}
						{!visible && !slate && (
							<Stack sx={{ height: '100%' }} justifyContent="center" alignItems="center">
								<VideocamIcon />
								<Typography variant="caption">Wachtbeeld</Typography>
							</Stack>
						)}
						<Box
							sx={{
								position: 'absolute',
								top: 0,
								left: 0,
								right: 0,
								p: 0.5,
								background: '#0009',
								textAlign: 'center',
								fontSize: { xs: 10, md: 13 },
							}}
						>
							{visible ? camera.name : 'Wachtbeeld'}
							{i === 0 && visible ? ' · AUDIO' : ''}
						</Box>
					</Box>
				);
			})}
		</Box>
	);
}

export default function Studio({ restreamer }) {
	const { state, error, busy, request } = useStudio(restreamer);
	const slates = useSlates(restreamer, state?.cameras);
	const [channels, setChannels] = React.useState([]);
	const [channel, setChannel] = React.useState('');
	const [alias, setAlias] = React.useState('');
	const [scene, setScene] = React.useState(null);
	const [editing, setEditing] = React.useState(null);
	const [interval, setIntervalValue] = React.useState('180');
	const [notice, setNotice] = React.useState('');
	const [actionError, setActionError] = React.useState('');
	const [previewVersion, setPreviewVersion] = React.useState(0);
	React.useEffect(() => {
		restreamer
			.StudioRequest('GET', '/channels')
			.then(setChannels)
			.catch(() => {});
	}, [restreamer]);
	React.useEffect(() => {
		if (state?.rotation.interval_seconds) setIntervalValue(String(state.rotation.interval_seconds));
	}, [state?.rotation.interval_seconds]);
	const patchProgram = (body) => request('PATCH', '/program', body);
	const switchCamera = (camera) => request('POST', '/program/switch', { camera });
	const provision = async () => {
		setActionError('');
		try {
			const result = await request('POST', '/program/channel');
			if (result) {
				await restreamer.ReloadChannels();
				await restreamer.UpdatePlayer(result.channel_id);
				const metadata = await restreamer.GetIngestMetadata(result.channel_id);
				await restreamer.UpsertIngestSnapshot(result.channel_id, metadata.control);
				await restreamer.StartIngestSnapshot(result.channel_id);
				setNotice('Woody Hoofdstream is beschikbaar. Open het kanaal om publicaties toe te voegen.');
			}
		} catch (e) {
			setActionError(e.message || 'Het hoofdkanaal kon niet worden ingesteld.');
		}
	};
	const uploadSlate = (event) => {
		const file = event.target.files?.[0];
		const cid = editing?.cid;
		event.target.value = '';
		if (!file || !cid) return;
		setActionError('');
		if (file.size > 4 * 1024 * 1024) {
			setActionError('De afbeelding mag maximaal 4 MB zijn.');
			return;
		}
		const reader = new FileReader();
		reader.onerror = () => setActionError('De afbeelding kon niet worden gelezen.');
		reader.onload = async () => {
			if (await request('PUT', `/cameras/${cid}/slate`, { image_data: reader.result })) {
				setNotice('Eigen wachtbeeld opgeslagen. Toon het met Wachtbeeld tonen of Verbergen + dempen.');
			}
		};
		reader.readAsDataURL(file);
	};
	const add = async () => {
		if (await request('POST', '/cameras', { channel_id: channel, alias, chat_enabled: false })) {
			setChannel('');
			setAlias('');
		}
	};
	if (!state) return <Box sx={{ p: 4 }}>{error ? <Alert severity="error">{error}</Alert> : <CircularProgress />}</Box>;
	const { program, cameras, rotation } = state;
	const list = Object.entries(cameras);
	return (
		<Box
			data-woody-page="studio"
			sx={{
				pb: 10,
				px: { xs: 2, sm: 0 },
				'& .MuiButton-textPrimary:not(.Mui-disabled)': { color: 'text.primary' },
				'& .MuiButton-root': { minHeight: 40 },
				'& .MuiCard-root': { p: 0, border: '1px solid', borderColor: 'divider', boxShadow: 'none' },
				'& .MuiCardContent-root': { p: { xs: 2, md: 3 }, '&:last-child': { pb: { xs: 2, md: 3 } } },
			}}
		>
			<Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2} mb={3}>
				<Box>
					<Typography variant="h4">Studio</Typography>
					<Typography color="text.secondary">Eén uitzending · tot 13 camera’s · geluid volgt het grote beeld</Typography>
				</Box>
				<Stack direction="row" flexWrap="wrap" useFlexGap spacing={1}>
					<Chip label={`Mixer: ${state.engine?.state || 'onbekend'}`} color={state.engine?.state === 'running' ? 'success' : 'warning'} />
					{state.engine?.output_fps !== undefined && (
						<Chip label={`Encoder: ${state.engine.output_fps} / ${state.engine.fps} fps`} color={state.engine.output_fps >= state.engine.fps * 0.85 ? 'success' : 'warning'} />
					)}
					<Button href="#/" variant="outlined">
						Naar Restreamer
					</Button>
					<Button href="#/chatbot" variant="outlined">
						Chatbot
					</Button>
				</Stack>
			</Stack>
			{(error || actionError) && (
				<Alert severity="error" sx={{ mb: 2 }}>
					{error || actionError}
				</Alert>
			)}
			{notice && (
				<Alert severity="success" onClose={() => setNotice('')} sx={{ mb: 2 }}>
					{notice}
				</Alert>
			)}
			{program.safe && (
				<Alert severity="warning" sx={{ mb: 2 }}>
					Algemeen wachtbeeld actief. Chatbediening is vergrendeld.
				</Alert>
			)}
			{list.length === 0 && (
				<Alert severity="info" sx={{ mb: 3 }}>
					Koppel hieronder eerst een bestaand camerakanaal aan Studio. Maak daarna het hoofdkanaal gereed en kies een indeling.
				</Alert>
			)}
			<Grid container spacing={3}>
				<Grid item xs={12} md={8}>
					<Card>
						<CardContent>
							<Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1} mb={2}>
								<Typography variant="h6">Woody Hoofdstream</Typography>
								<Button variant="outlined" disabled={busy} onClick={provision}>
									Hoofdkanaal gereedmaken
								</Button>
							</Stack>
							<Box
								data-testid="program-preview"
								sx={{
									position: 'relative',
									width: '100%',
									aspectRatio: '16 / 9',
									overflow: 'hidden',
									bgcolor: 'black',
									'& > .MuiGrid-root': { m: 0, width: '100%' },
									'& [data-vjs-player]': { width: '100%' },
								}}
							>
								<ProgramPreview key={previewVersion} source={restreamer.GetChannelAddress('hls+memfs', state.program_channel_id)} />
							</Box>
							<Stack direction="row" flexWrap="wrap" gap={1} mt={2}>
								<Button variant="contained" disabled={busy} onClick={() => patchProgram({ safe: false, layout: 'six' })}>
									1 groot + 5 klein
								</Button>
								<Button variant="outlined" disabled={busy} onClick={() => patchProgram({ safe: false, layout: 'full' })}>
									Volledig scherm
								</Button>
								<Button variant="outlined" disabled={busy} onClick={() => patchProgram({ pinned: !program.pinned })}>
									{program.pinned ? 'Vrijgeven' : 'Vastzetten'}
								</Button>
								<Button color="error" variant="contained" onClick={() => patchProgram({ safe: true })}>
									Alles naar wachtbeeld
								</Button>
							</Stack>
							<Button variant="outlined" href={`#/${state.program_channel_id}`} sx={{ mt: 2, mr: 1 }}>
								Open kanaal en publicaties
							</Button>
							<Button variant="outlined" onClick={() => setPreviewVersion((v) => v + 1)} sx={{ mt: 2 }}>
								Preview vernieuwen
							</Button>
						</CardContent>
					</Card>
					<Card sx={{ mt: 3 }}>
						<CardContent>
							<Stack direction="row" justifyContent="space-between" flexWrap="wrap" gap={1} mb={2}>
								<Typography variant="h6">Camera kiezen · momentopnamen</Typography>
								<Chip
									size="small"
									label={program.pinned ? 'Vastgezet' : rotation.enabled ? `Wissel over ${program.next_switch_in}s` : 'Handmatige regie'}
								/>
							</Stack>
							<CameraBoard
								slots={program.slots}
								cameras={cameras}
								slates={slates}
								restreamer={restreamer}
								safe={program.safe}
								full={program.layout === 'full'}
								color={program.border_color}
								border={program.border_width}
								onSwitch={switchCamera}
								disabled={busy}
							/>
							<Typography variant="caption" color="text.secondary">
								Deze foto’s vernieuwen elke vijf seconden. Klik op een klein kader om die camera groot te zetten. Bekijk het livebeeld hierboven.
							</Typography>
						</CardContent>
					</Card>
				</Grid>
				<Grid item xs={12} md={4}>
					<Card>
						<CardContent>
							<Typography variant="h6" mb={2}>
								Automatische ronde
							</Typography>
							<Stack direction={{ xs: 'column', sm: 'row', md: 'column', lg: 'row' }} spacing={1} alignItems="stretch">
								<TextField
									label="Interval in seconden"
									type="number"
									value={interval}
									onChange={(e) => setIntervalValue(e.target.value)}
									inputProps={{ min: 10, max: 86400 }}
									size="small"
								/>
								<Button
									variant="outlined"
									disabled={busy || !Number.isInteger(Number(interval)) || Number(interval) < 10 || Number(interval) > 86400}
									onClick={() => request('PUT', '/rotation', { ...rotation, interval_seconds: Number(interval) })}
								>
									Opslaan
								</Button>
							</Stack>
							<Button
								variant="outlined"
								sx={{ mt: 2 }}
								startIcon={rotation.enabled ? <PauseIcon /> : <PlayArrowIcon />}
								disabled={busy}
								onClick={() => request('PUT', '/rotation', { ...rotation, enabled: !rotation.enabled })}
							>
								{rotation.enabled ? 'Ronde pauzeren' : 'Ronde hervatten'}
							</Button>
							<Stack mt={2} spacing={1}>
								{rotation.order.map((cid, index) => (
									<Stack key={cid} direction="row" alignItems="center" spacing={1}>
										<Typography sx={{ flex: 1 }}>
											{index + 1}. {cameras[cid]?.name}
										</Typography>
										<Button
											variant="outlined"
											size="small"
											disabled={busy || index === 0}
											aria-label={`Zet ${cameras[cid]?.name} eerder`}
											onClick={() => {
												const order = [...rotation.order];
												[order[index - 1], order[index]] = [order[index], order[index - 1]];
												request('PUT', '/rotation', { ...rotation, order });
											}}
										>
											↑
										</Button>
									</Stack>
								))}
							</Stack>
						</CardContent>
					</Card>
					<Card sx={{ mt: 3 }}>
						<CardContent>
							<Typography variant="h6" mb={2}>
								Scènes
							</Typography>
							<Stack spacing={1}>
								{Object.values(state.scenes).map((s) => (
									<Stack key={s.alias} direction="row" spacing={1}>
										<Button
											variant="outlined"
											sx={{ flex: 1, justifyContent: 'flex-start' }}
											disabled={busy}
											onClick={() => request('POST', `/scenes/${s.alias}/apply`)}
										>
											{s.name}
										</Button>
										<Button variant="outlined" size="small" onClick={() => setScene({ ...s })}>
											Bewerk
										</Button>
										<Button
											variant="outlined"
											size="small"
											color="error"
											disabled={busy}
											onClick={() => request('DELETE', `/scenes/${s.alias}`)}
										>
											Wis
										</Button>
									</Stack>
								))}
							</Stack>
							<Button
								variant="outlined"
								sx={{ mt: 2 }}
								onClick={() => setScene({ alias: '', name: '', layout: program.layout, cameras: [...program.slots], chat_enabled: false })}
							>
								Scène samenstellen
							</Button>
						</CardContent>
					</Card>
					<Card sx={{ mt: 3 }}>
						<CardContent>
							<Typography variant="h6" mb={2}>
								Kaderranden
							</Typography>
							<Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
								<TextField
									label="Kleur"
									type="color"
									value={program.border_color}
									onChange={(e) => patchProgram({ border_color: e.target.value })}
								/>
								<TextField
									select
									label="Dikte"
									value={program.border_width}
									onChange={(e) => patchProgram({ border_width: Number(e.target.value) })}
								>
									{[0, 2, 4, 6, 8, 12].map((v) => (
										<MenuItem key={v} value={v}>
											{v}px
										</MenuItem>
									))}
								</TextField>
							</Stack>
						</CardContent>
					</Card>
				</Grid>
				<Grid item xs={12}>
					<Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1} mb={2}>
						<Typography variant="h5">
							Camera’s{' '}
							<Typography component="span" color="text.secondary">
								{list.length}/13
							</Typography>
						</Typography>
						<Button variant="outlined" href="#/">
							Bestaande kanalen beheren
						</Button>
					</Stack>
					<Card sx={{ mb: 2 }}>
						<CardContent>
							<Stack direction={{ xs: 'column', sm: 'row' }} flexWrap="wrap" useFlexGap spacing={2}>
								<TextField
									select
									label="Bestaand Restreamer-kanaal"
									value={channel}
									onChange={(e) => setChannel(e.target.value)}
									sx={{ minWidth: { sm: 240 }, flex: 1 }}
									size="small"
								>
									{channels.map((c) => (
										<MenuItem key={c.channel_id} value={c.channel_id}>
											{c.name}
										</MenuItem>
									))}
								</TextField>
								<TextField label="Chatalias, bijvoorbeeld tuin" value={alias} onChange={(e) => setAlias(e.target.value)} size="small" />
								<Button
									variant="contained"
									disabled={busy || !channel || !/^[a-z][a-z0-9-]{0,31}$/.test(alias) || list.length >= 13}
									onClick={add}
								>
									Camera toevoegen
								</Button>
								<Button
									variant="outlined"
									onClick={async () => {
										const result = await request('GET', '/channels');
										if (result) setChannels(result);
									}}
								>
									Kanalen vernieuwen
								</Button>
							</Stack>
						</CardContent>
					</Card>
					<Grid container spacing={2}>
						{list.map(([cid, c]) => (
							<Grid item key={cid} xs={12} sm={6} md={4} xl={3}>
								<Card sx={{ border: c.hidden ? '1px solid #ef5350' : undefined }}>
									<CardContent>
										<Stack direction="row" justifyContent="space-between" alignItems="center">
											<Typography variant="h6">{c.name}</Typography>
											<Chip
												size="small"
												label={c.hidden ? 'Verborgen' : c.state}
												color={c.hidden ? 'error' : c.state === 'online' ? 'success' : 'default'}
											/>
										</Stack>
										{!c.hidden && c.state !== 'online' && c.reason && (
											<Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
												{sourceReasons[c.reason] || 'Studio ontvangt nog geen camerabeeld.'}
											</Typography>
										)}
										<Typography variant="body2" color="text.secondary">
											!camera {c.alias}
											{program.audio_camera === cid ? ' · Audio actief' : ''}
										</Typography>
										<Stack direction="row" flexWrap="wrap" useFlexGap spacing={1} mt={2}>
											<Button variant="outlined" disabled={busy || c.hidden || c.state !== 'online'} onClick={() => switchCamera(cid)}>
												Groot zetten
											</Button>
											<Button
												variant="contained"
												color={c.hidden ? 'success' : 'error'}
												onClick={() => request('PUT', `/cameras/${cid}/hidden`, { hidden: !c.hidden })}
											>
												{c.hidden ? 'Vrijgeven' : 'Verbergen + dempen'}
											</Button>
										</Stack>
										<Stack direction="row" justifyContent="space-between" mt={1}>
											<FormControlLabel
												label="Via chat"
												control={
													<Switch
														checked={c.chat_enabled}
														disabled={busy}
														onChange={(e) => request('PATCH', `/cameras/${cid}`, { chat_enabled: e.target.checked })}
													/>
												}
											/>
											<Button variant="outlined" onClick={() => setEditing({ cid, alias: c.alias })}>
												Bewerk
											</Button>
										</Stack>
									</CardContent>
								</Card>
							</Grid>
						))}
					</Grid>
				</Grid>
			</Grid>
			<Dialog open={!!scene} onClose={() => setScene(null)} fullWidth maxWidth="sm" sx={dialogLayout}>
				<DialogTitle>Scène samenstellen</DialogTitle>
				<DialogContent>
					<Stack spacing={2} mt={1}>
						<TextField label="Naam" value={scene?.name || ''} onChange={(e) => setScene({ ...scene, name: e.target.value })} />
						<TextField label="Chatalias" value={scene?.alias || ''} onChange={(e) => setScene({ ...scene, alias: e.target.value })} />
						<TextField select label="Indeling" value={scene?.layout || 'six'} onChange={(e) => setScene({ ...scene, layout: e.target.value })}>
							{[
								['six', '1 groot + 5 klein'],
								['full', 'Volledig scherm'],
								['safe', 'Wachtbeeld'],
							].map(([v, text]) => (
								<MenuItem key={v} value={v}>
									{text}
								</MenuItem>
							))}
						</TextField>
						{scene &&
							scene.layout !== 'safe' &&
							Array.from({ length: scene.layout === 'full' ? 1 : 6 }, (_, i) => (
								<TextField
									select
									key={i}
									label={i === 0 ? 'Grote camera' : `Klein kader ${i}`}
									value={scene.cameras[i] || ''}
									onChange={(e) => {
										const cams = [...scene.cameras];
										cams[i] = e.target.value;
										setScene({ ...scene, cameras: cams });
									}}
								>
									<MenuItem value="">Wachtbeeld</MenuItem>
									{list.map(([cid, c]) => (
										<MenuItem value={cid} key={cid}>
											{c.name}
										</MenuItem>
									))}
								</TextField>
							))}
						<FormControlLabel
							label="Scène beschikbaar via chat"
							control={<Switch checked={scene?.chat_enabled || false} onChange={(e) => setScene({ ...scene, chat_enabled: e.target.checked })} />}
						/>
						<Typography variant="caption">
							Alle gebruikte camera’s moeten ook voor chat vrijgegeven zijn. Verborgen camera’s blijven afgeschermd.
						</Typography>
					</Stack>
				</DialogContent>
				<DialogActions>
					<Button variant="outlined" onClick={() => setScene(null)}>
						Annuleren
					</Button>
					<Button
						variant="outlined"
						disabled={busy || !scene?.name || !/^[a-z][a-z0-9-]{0,31}$/.test(scene?.alias || '')}
						onClick={async () => {
							if (
								await request('PUT', '/scenes', {
									...scene,
									cameras: scene.layout === 'safe' ? [] : scene.cameras.map((c) => c || null).slice(0, scene.layout === 'full' ? 1 : 6),
								})
							)
								setScene(null);
						}}
					>
						Opslaan
					</Button>
				</DialogActions>
			</Dialog>
			<Dialog open={!!editing} onClose={() => setEditing(null)} fullWidth maxWidth="sm" sx={dialogLayout}>
				<DialogTitle>Camera bewerken</DialogTitle>
				<DialogContent>
					<TextField
						sx={{ mt: 1 }}
						label="Chatalias"
						value={editing?.alias || ''}
						onChange={(e) => setEditing({ ...editing, alias: e.target.value })}
					/>
					<Stack spacing={2} sx={{ mt: 3 }}>
						<Typography variant="h6">Eigen wachtbeeld</Typography>
						<Typography variant="body2">
							PNG, JPG of WebP, maximaal 4 MB. Het beeld past binnen 16:9; het geluid van deze camera gaat uit wanneer het wachtbeeld wordt
							getoond.
						</Typography>
						{(actionError || error) && <Alert severity="error">{actionError || error}</Alert>}
						{editing && slates[editing.cid] && (
							<Box
								component="img"
								alt="Eigen wachtbeeld"
								src={slates[editing.cid].image_data}
								sx={{ width: '100%', maxHeight: 200, objectFit: 'contain', bgcolor: 'black' }}
							/>
						)}
						<Stack direction="row" flexWrap="wrap" useFlexGap spacing={1}>
							<Button component="label" variant="outlined" disabled={busy}>
								Afbeelding uploaden
								<input type="file" hidden aria-label="Wachtbeeldbestand" accept="image/png,image/jpeg,image/webp" onChange={uploadSlate} />
							</Button>
							<Button
								variant="outlined"
								disabled={busy || !cameras[editing?.cid]?.slate_version}
								onClick={() => request('DELETE', `/cameras/${editing.cid}/slate`)}
							>
								Afbeelding verwijderen
							</Button>
						</Stack>
						<Button
							variant="outlined"
							disabled={!cameras[editing?.cid]?.slate_version}
							onClick={() => request('PUT', `/cameras/${editing.cid}/hidden`, { hidden: !cameras[editing.cid].hidden })}
						>
							{cameras[editing?.cid]?.hidden ? 'Camera weer tonen' : 'Wachtbeeld tonen'}
						</Button>
						<Typography variant="caption">
							Het eigen beeld verschijnt ook bij bronuitval, zolang deze camera aan het kader is toegewezen. Gebruik Vastzetten om automatische
							wissels te pauzeren. Alles naar wachtbeeld gebruikt het algemene wachtbeeld.
						</Typography>
					</Stack>
				</DialogContent>
				<DialogActions>
					<Button
						variant="outlined"
						color="error"
						disabled={busy}
						onClick={async () => {
							if (await request('DELETE', `/cameras/${editing.cid}`)) setEditing(null);
						}}
					>
						Uit regie verwijderen
					</Button>
					<Button
						variant="outlined"
						disabled={busy}
						onClick={async () => {
							const camera = cameras[editing.cid];
							if (camera) await request('POST', '/cameras', { channel_id: editing.cid, alias: camera.alias, chat_enabled: camera.chat_enabled });
						}}
					>
						Bron vernieuwen
					</Button>
					<Button
						variant="outlined"
						disabled={busy || !/^[a-z][a-z0-9-]{0,31}$/.test(editing?.alias || '')}
						onClick={async () => {
							if (await request('PATCH', `/cameras/${editing.cid}`, { alias: editing.alias })) setEditing(null);
						}}
					>
						Opslaan
					</Button>
				</DialogActions>
			</Dialog>
		</Box>
	);
}
