import React from 'react';
import { Alert, Button, Stack } from '@mui/material';

// Keep the normal Restreamer header, navigation and channels available if a
// Studio view fails. An unexpected rendering error must never empty the app.
export default class StudioBoundary extends React.Component {
	state = { failed: false, attempt: 0 };
	static getDerivedStateFromError() {
		return { failed: true };
	}
	render() {
		if (this.state.failed) {
			return (
				<Stack spacing={2} sx={{ pb: 8 }}>
					<Alert severity="error">Studio kon niet worden weergegeven. Probeer opnieuw of ga terug naar Restreamer.</Alert>
					<Stack direction="row" spacing={2}>
						<Button variant="outlined" onClick={() => this.setState(({ attempt }) => ({ failed: false, attempt: attempt + 1 }))}>
							Studio opnieuw laden
						</Button>
						<Button variant="outlined" href="#/">
							Naar Restreamer
						</Button>
					</Stack>
				</Stack>
			);
		}
		return <React.Fragment key={this.state.attempt}>{this.props.children}</React.Fragment>;
	}
}
