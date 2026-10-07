const axios = require('axios');

class TrackMageClient {
  constructor(clientId, clientSecret) {
    if (!clientId || !clientSecret) {
      throw new Error('clientId and clientSecret are required');
    }
    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.apiUrl = 'https://api.trackmage.com';
    this.accessToken = null;
    this.tokenExpiresAt = 0;
    this.axios = axios.create({ baseURL: this.apiUrl });
    this.refreshPromise = null;

    // Request interceptor for token management
    this.axios.interceptors.request.use(async (config) => {
      if (!this.accessToken || Date.now() >= this.tokenExpiresAt) {
        await this.refreshToken();
      }
      config.headers.Authorization = `Bearer ${this.accessToken}`;
      return config;
    });

    // Response interceptor for 401 handling
    this.axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          await this.refreshToken();
          error.config.headers.Authorization = `Bearer ${this.accessToken}`;
          return this.axios(error.config);
        }
        throw error.response?.data?.['hydra:description'] || error.message;
      }
    );
  }

  async refreshToken() {
    if (this.refreshPromise) return this.refreshPromise;
    this.refreshPromise = axios
      .get(`${this.apiUrl}/oauth/v2/token`, {
        params: {
          grant_type: 'client_credentials',
          client_id: this.clientId,
          client_secret: this.clientSecret,
        },
      })
      .then((response) => {
        this.accessToken = response.data.access_token;
        this.tokenExpiresAt = Date.now() + response.data.expires_in * 1000 - 60000; // Refresh 1 min early
        this.refreshPromise = null;
        return;
      })
      .catch((error) => {
        this.refreshPromise = null;
        throw new Error('Authentication failed: ' + (error.response?.data?.error_description || error.message));
      });
    return this.refreshPromise;
  }

  async listResources(type, { workspaceId, filters = {}, page = 1, itemsPerPage = 30 } = {}) {
    let url;
    switch (type) {
      case 'shipments':
      case 'orders':
        if (!workspaceId) throw new Error('workspaceId is required for ' + type);
        url = `/workspaces/${workspaceId}/${type}`;
        break;
      case 'workspaces':
        url = '/workspaces';
        break;
      case 'carriers':
        url = '/public/carriers';
        break;
      case 'tracking_statuses':
        url = '/public/tracking_statuses';
        break;
      default:
        throw new Error('Unsupported resource type: ' + type);
    }
    const response = await this.axios.get(url, { params: { ...filters, page, itemsPerPage } });
    const items = response.data['hydra:member'] || [];
    const nextCursor = items.length === itemsPerPage ? String(page + 1) : null;
    return { items, nextCursor };
  }

  async getResource(type, id) {
    const urlMap = {
      shipments: `/shipments/${id}`,
      orders: `/orders/${id}`,
      workspaces: `/workspaces/${id}`,
      carriers: `/public/carriers/${id}`,
      tracking_statuses: `/public/tracking_statuses/${id}`,
    };
    if (!urlMap[type]) throw new Error('Unsupported resource type: ' + type);
    const response = await this.axios.get(urlMap[type]);
    return response.data;
  }

  async createShipment(workspaceId, data) {
    const payload = { ...data, workspace: `/workspaces/${workspaceId}` };
    const response = await this.axios.post('/shipments', payload, {
      headers: { 'Content-Type': 'application/ld+json' },
    });
    return response.data;
  }

  async createOrder(workspaceId, data) {
    const payload = { ...data, workspace: `/workspaces/${workspaceId}` };
    const response = await this.axios.post('/orders', payload, {
      headers: { 'Content-Type': 'application/ld+json' },
    });
    return response.data;
  }

  async getCheckpoints(shipmentId) {
    const response = await this.axios.get(`/shipments/${shipmentId}/checkpoints`, {
      params: { 'order[checkpointDate]': 'desc', '_locale': 'mixed' },
    });
    return response.data['hydra:member'] || [];
  }

  async updateOrder(orderId, data) {
    const response = await this.axios.put(`/orders/${orderId}`, data, {
      headers: { 'Content-Type': 'application/ld+json' },
    });
    return response.data;
  }

  async updateShipment(shipmentId, data) {
    const response = await this.axios.put(`/shipments/${shipmentId}`, data, {
      headers: { 'Content-Type': 'application/ld+json' },
    });
    return response.data;
  }

  async detectCarrier(trackingNumber) {
    const response = await this.axios.get(`/tracking_numbers/${trackingNumber}/detect-carrier`);
    return response.data;
  }

  async retrackShipments(workspaceId, trackingNumbers) {
    const response = await this.axios.post('/check_tracking_numbers', {
      workspaceId,
      trackingNumbers,
    }, {
      headers: { 'Content-Type': 'application/ld+json' },
    });
    return response.data;
  }
}

module.exports = TrackMageClient;