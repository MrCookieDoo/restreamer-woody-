import React from 'react';

export default function useStudio(restreamer) {
	const [state, setState] = React.useState(null);
	const [loadError, setLoadError] = React.useState('');
	const [actionError, setActionError] = React.useState('');
	const [busy, setBusy] = React.useState(false);
	const mounted = React.useRef(true);
	const pending = React.useRef(0);
	const receive = React.useCallback((value) => {
		setState((previous) => (previous && previous.revision > value.revision ? previous : { ...previous, ...value }));
	}, []);
	const refresh = React.useCallback(async () => {
		try {
			const value = await restreamer.StudioRequest('GET', '/state');
			if (mounted.current) {
				receive(value);
				setLoadError('');
			}
		} catch (e) {
			if (mounted.current) setLoadError(e.message);
		}
	}, [restreamer, receive]);
	React.useEffect(() => {
		mounted.current = true;
		let timer;
		const poll = async () => {
			await refresh();
			if (mounted.current) timer = setTimeout(poll, 1000);
		};
		poll();
		return () => {
			mounted.current = false;
			clearTimeout(timer);
		};
	}, [refresh]);
	const request = async (method, path, body) => {
		pending.current += 1;
		setBusy(true);
		try {
			const value = await restreamer.StudioRequest(method, path, body);
			if (mounted.current) {
				if (value?.program) receive(value);
				setActionError('');
			}
			if (!value?.program) await refresh();
			return value;
		} catch (e) {
			if (mounted.current) setActionError(e.message);
			return null;
		} finally {
			pending.current -= 1;
			if (mounted.current) setBusy(pending.current > 0);
		}
	};
	return { state, error: actionError || loadError, busy, request };
}
