import React from 'react';
import { Button, Stack, Typography } from '@mui/material';
import LayersIcon from '@mui/icons-material/Layers';

export default function StudioLink() {
	return (
		<Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} justifyContent="space-between" gap={2} sx={{ mb: 2 }}>
			<Typography color="text.secondary">Combineer camera’s en bedien je hoofdstream vanuit Studio.</Typography>
			<Button component="a" href="#/studio" variant="outlined" color="primary" startIcon={<LayersIcon />}>
				Studio openen
			</Button>
		</Stack>
	);
}
