import React from 'react';

export default function useSlates(restreamer, cameras) {
	const [images, setImages] = React.useState({});
	const cache = React.useRef({});
	const versions = JSON.stringify(
		Object.entries(cameras || {})
			.filter(([, camera]) => camera.slate_version)
			.map(([cid, camera]) => [cid, camera.slate_version]),
	);
	React.useEffect(() => {
		let cancelled = false;
		const manifest = Object.fromEntries(JSON.parse(versions));
		cache.current = Object.fromEntries(Object.entries(cache.current).filter(([cid, image]) => manifest[cid] === image.version));
		setImages({ ...cache.current });
		for (const [cid, version] of Object.entries(manifest)) {
			if (cache.current[cid]?.version === version) continue;
			restreamer
				.StudioRequest('GET', `/cameras/${cid}/slate`)
				.then((image) => {
					if (cancelled || image.version !== version) return;
					cache.current[cid] = image;
					setImages({ ...cache.current });
				})
				.catch(() => {});
		}
		return () => {
			cancelled = true;
		};
	}, [restreamer, versions]);
	return images;
}
