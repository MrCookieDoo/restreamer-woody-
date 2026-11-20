import Restreamer from './restreamer';

function client() {
	const rs = Object.create(Restreamer.prototype);
	rs.api = { _call: jest.fn() };
	rs.RefreshToken = jest.fn(async () => true);
	rs._dispatchEvent = jest.fn();
	return rs;
}

beforeAll(() => {
	// Jest's jsdom uses an older AbortSignal; production browsers implement timeout.
	if (!AbortSignal.timeout) AbortSignal.timeout = () => new AbortController().signal;
});

test('a Studio connection failure does not invalidate the normal Restreamer UI', async () => {
	const rs = client();
	rs.api._call.mockResolvedValue({ val: null, err: { code: -1, message: 'Studio offline' } });
	await expect(rs.StudioRequest('GET', '/state')).rejects.toThrow('Studio offline');
	expect(rs._dispatchEvent).not.toHaveBeenCalled();
});

test('Studio refreshes an expired Core access token and retries the same action once', async () => {
	const rs = client();
	rs.api._call.mockResolvedValueOnce({ val: null, err: { code: 401 } }).mockResolvedValueOnce({ val: { revision: 2 }, err: null });
	await expect(rs.StudioRequest('PATCH', '/program', { safe: true })).resolves.toEqual({ revision: 2 });
	expect(rs.RefreshToken).toHaveBeenCalledTimes(1);
	expect(rs.api._call).toHaveBeenCalledTimes(2);
	expect(rs.api._call).toHaveBeenLastCalledWith('PATCH', '/woody/v1/program', expect.objectContaining({ body: '{"safe":true}', signal: expect.anything() }));
});

test('validation errors are readable text rather than objects passed to React', async () => {
	const rs = client();
	rs.api._call.mockResolvedValue({ val: null, err: { code: 422, message: { detail: [{ msg: 'Invalid input' }] } } });
	await expect(rs.StudioRequest('PUT', '/scenes', {})).rejects.toThrow('Controleer de invoer');
});
