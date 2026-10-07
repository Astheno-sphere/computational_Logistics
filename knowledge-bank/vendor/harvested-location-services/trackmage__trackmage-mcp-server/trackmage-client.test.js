const TrackMageClient = require('./trackmage-client');
const axios = require('axios');
jest.mock('axios');

describe('TrackMageClient', () => {
  let client;

  beforeEach(() => {
    axios.create.mockReturnValue({
      interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
    });
    client = new TrackMageClient('test_id', 'test_secret');
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('constructor throws without credentials', () => {
    expect(() => new TrackMageClient()).toThrow('clientId and clientSecret are required');
  });

  test('refreshToken sets access token', async () => {
    axios.get.mockResolvedValue({
      data: { access_token: 'token123', expires_in: 3600 },
    });
    await client.refreshToken();
    expect(client.accessToken).toBe('token123');
    expect(client.tokenExpiresAt).toBeGreaterThan(Date.now());
  });

  test('listResources handles shipments', async () => {
    client.axios.get.mockResolvedValue({
      data: { 'hydra:member': [{ id: 's1', trackingNumber: 'TN1' }] },
    });
    const result = await client.listResources('shipments', { workspaceId: 'w1' });
    expect(result).toEqual({ items: [{ id: 's1', trackingNumber: 'TN1' }], nextCursor: null });
    expect(client.axios.get).toHaveBeenCalledWith('/workspaces/w1/shipments', expect.any(Object));
  });

  test('getResource fetches shipment', async () => {
    client.axios.get.mockResolvedValue({ data: { id: 's1' } });
    const result = await client.getResource('shipments', 's1');
    expect(result).toEqual({ id: 's1' });
    expect(client.axios.get).toHaveBeenCalledWith('/shipments/s1');
  });

  test('createShipment posts data', async () => {
    client.axios.post.mockResolvedValue({ data: { id: 's1' } });
    const result = await client.createShipment('w1', { trackingNumber: 'TN1' });
    expect(result).toEqual({ id: 's1' });
    expect(client.axios.post).toHaveBeenCalledWith(
      '/shipments',
      { trackingNumber: 'TN1', workspace: '/workspaces/w1' },
      expect.any(Object)
    );
  });

  test('createOrder posts data', async () => {
    client.axios.post.mockResolvedValue({ data: { id: 'o1' } });
    const result = await client.createOrder('w1', { orderNumber: 'ORD123' });
    expect(result).toEqual({ id: 'o1' });
    expect(client.axios.post).toHaveBeenCalledWith(
      '/orders',
      { orderNumber: 'ORD123', workspace: '/workspaces/w1' },
      expect.any(Object)
    );
  });

  test('getCheckpoints fetches shipment checkpoints', async () => {
    client.axios.get.mockResolvedValue({
      data: { 'hydra:member': [{ id: 'c1', status: 'delivered' }] },
    });
    const result = await client.getCheckpoints('s1');
    expect(result).toEqual([{ id: 'c1', status: 'delivered' }]);
    expect(client.axios.get).toHaveBeenCalledWith('/shipments/s1/checkpoints', expect.any(Object));
  });

  test('updateOrder updates order data', async () => {
    client.axios.put.mockResolvedValue({ data: { id: 'o1', status: 'fulfilled' } });
    const result = await client.updateOrder('o1', { status: 'fulfilled' });
    expect(result).toEqual({ id: 'o1', status: 'fulfilled' });
    expect(client.axios.put).toHaveBeenCalledWith('/orders/o1', { status: 'fulfilled' }, expect.any(Object));
  });

  test('updateShipment updates shipment data', async () => {
    client.axios.put.mockResolvedValue({ data: { id: 's1', status: 'delivered' } });
    const result = await client.updateShipment('s1', { status: 'delivered' });
    expect(result).toEqual({ id: 's1', status: 'delivered' });
    expect(client.axios.put).toHaveBeenCalledWith('/shipments/s1', { status: 'delivered' }, expect.any(Object));
  });

  test('detectCarrier detects carrier for tracking number', async () => {
    client.axios.get.mockResolvedValue({ data: { carrier: 'ups' } });
    const result = await client.detectCarrier('1Z123456');
    expect(result).toEqual({ carrier: 'ups' });
    expect(client.axios.get).toHaveBeenCalledWith('/tracking_numbers/1Z123456/detect-carrier');
  });

  test('retrackShipments retracks shipments', async () => {
    client.axios.post.mockResolvedValue({ data: { processed: 2 } });
    const trackingNumbers = [{ number: 'TN1' }, { number: 'TN2' }];
    const result = await client.retrackShipments('w1', trackingNumbers);
    expect(result).toEqual({ processed: 2 });
    expect(client.axios.post).toHaveBeenCalledWith(
      '/check_tracking_numbers',
      { workspaceId: 'w1', trackingNumbers },
      expect.any(Object)
    );
  });

  test('listResources handles orders', async () => {
    client.axios.get.mockResolvedValue({
      data: { 'hydra:member': [{ id: 'o1', orderNumber: 'ORD1' }] },
    });
    const result = await client.listResources('orders', { workspaceId: 'w1' });
    expect(result).toEqual({ items: [{ id: 'o1', orderNumber: 'ORD1' }], nextCursor: null });
    expect(client.axios.get).toHaveBeenCalledWith('/workspaces/w1/orders', expect.any(Object));
  });

  test('listResources handles workspaces', async () => {
    client.axios.get.mockResolvedValue({
      data: { 'hydra:member': [{ id: 'w1', name: 'Workspace 1' }] },
    });
    const result = await client.listResources('workspaces');
    expect(result).toEqual({ items: [{ id: 'w1', name: 'Workspace 1' }], nextCursor: null });
    expect(client.axios.get).toHaveBeenCalledWith('/workspaces', expect.any(Object));
  });

  test('listResources handles carriers', async () => {
    client.axios.get.mockResolvedValue({
      data: { 'hydra:member': [{ id: 'ups', name: 'UPS' }] },
    });
    const result = await client.listResources('carriers');
    expect(result).toEqual({ items: [{ id: 'ups', name: 'UPS' }], nextCursor: null });
    expect(client.axios.get).toHaveBeenCalledWith('/public/carriers', expect.any(Object));
  });

  test('listResources handles tracking_statuses', async () => {
    client.axios.get.mockResolvedValue({
      data: { 'hydra:member': [{ id: 'delivered', name: 'Delivered' }] },
    });
    const result = await client.listResources('tracking_statuses');
    expect(result).toEqual({ items: [{ id: 'delivered', name: 'Delivered' }], nextCursor: null });
    expect(client.axios.get).toHaveBeenCalledWith('/public/tracking_statuses', expect.any(Object));
  });

  test('listResources throws for unsupported type', async () => {
    await expect(client.listResources('invalid')).rejects.toThrow('Unsupported resource type: invalid');
  });

  test('listResources throws when workspaceId missing for shipments', async () => {
    await expect(client.listResources('shipments')).rejects.toThrow('workspaceId is required for shipments');
  });

  test('getResource handles all resource types', async () => {
    const types = ['shipments', 'orders', 'workspaces', 'carriers', 'tracking_statuses'];
    
    for (const type of types) {
      client.axios.get.mockResolvedValue({ data: { id: 'test' } });
      const result = await client.getResource(type, 'test');
      expect(result).toEqual({ id: 'test' });
    }
  });

  test('getResource throws for unsupported type', async () => {
    await expect(client.getResource('invalid', 'id')).rejects.toThrow('Unsupported resource type: invalid');
  });
});