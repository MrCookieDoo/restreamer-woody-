import React from 'react';
import { Route, Navigate, Routes, HashRouter as DOMRouter } from 'react-router-dom';

import Views from './views';
import Studio from './views/Woody/Studio';
import Chatbot from './views/Woody/Chatbot';
import StudioBoundary from './views/Woody/StudioBoundary';

export default function Router(props) {
	if (props.restreamer === null) {
		return null;
	}

	const channelid = props.restreamer.GetCurrentChannelID();

	return (
		<DOMRouter>
			<Routes>
				<Route path="/" element={<Views.ChannelSelect channelid={channelid} />} />
				<Route
					path="/studio"
					element={
						<StudioBoundary key="studio">
							<Studio restreamer={props.restreamer} />
						</StudioBoundary>
					}
				/>
				<Route
					path="/chatbot"
					element={
						<StudioBoundary key="chatbot">
							<Chatbot restreamer={props.restreamer} />
						</StudioBoundary>
					}
				/>
				<Route path="/playersite" element={<Views.Playersite restreamer={props.restreamer} />} />
				<Route path="/settings" element={<Views.Settings restreamer={props.restreamer} />} />
				<Route path="/settings/:tab" element={<Views.Settings restreamer={props.restreamer} />} />
				<Route path="/:channelid" element={<Views.Main key={channelid} restreamer={props.restreamer} />} />
				<Route path="/:channelid/edit" element={<Views.Edit key={channelid} restreamer={props.restreamer} />} />
				<Route path="/:channelid/edit/wizard" element={<Views.Wizard key={channelid} restreamer={props.restreamer} />} />
				<Route path="/:channelid/edit/:tab" element={<Views.Edit key={channelid} restreamer={props.restreamer} />} />
				<Route path="/:channelid/publication" element={<Views.AddService key={channelid} restreamer={props.restreamer} />} />
				<Route path="/:channelid/publication/player" element={<Views.EditPlayer key={channelid} restreamer={props.restreamer} />} />
				<Route path="/:channelid/publication/:service/:index" element={<Views.EditService key={channelid} restreamer={props.restreamer} />} />
				<Route path="*" element={<Navigate to="/" replace />} />
			</Routes>
		</DOMRouter>
	);
}

Router.defaultProps = {
	restreamer: null,
};
