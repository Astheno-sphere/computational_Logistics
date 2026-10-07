const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { ListResourcesRequestSchema, ReadResourceRequestSchema, ListToolsRequestSchema, CallToolRequestSchema } = require('@modelcontextprotocol/sdk/types.js');
const TrackMageClient = require('./trackmage-client');
require('dotenv').config();

const { TRACKMAGE_CLIENT_ID, TRACKMAGE_CLIENT_SECRET, TRACKMAGE_WORKSPACE_ID } = process.env;
if (!TRACKMAGE_CLIENT_ID || !TRACKMAGE_CLIENT_SECRET || !TRACKMAGE_WORKSPACE_ID) {
  console.error('Error: TRACKMAGE_CLIENT_ID, TRACKMAGE_CLIENT_SECRET, and TRACKMAGE_WORKSPACE_ID must be set in .env');
  process.exit(1);
}

const client = new TrackMageClient(TRACKMAGE_CLIENT_ID, TRACKMAGE_CLIENT_SECRET);

const server = new Server(
  { name: 'trackmage', version: '0.1.0' },
  { capabilities: { resources: {}, tools: {} } }
);

// ListResources Handler
server.setRequestHandler(ListResourcesRequestSchema, async (request) => {
  const { type, filters = {}, cursor } = request.params;
  if (!type) throw new Error('Resource type is required');
  const page = cursor ? parseInt(cursor, 10) : 1;
  const params = { filters, page, workspaceId: filters.workspaceId || TRACKMAGE_WORKSPACE_ID };
  delete filters.workspaceId; // Remove from filters to avoid query param conflict
  const { items, nextCursor } = await client.listResources(type, params);
  return {
    resources: items.map((item) => ({
      uri: `trackmage:///${type}/${item.id}`,
      mimeType: 'application/json',
      name: item.title || item.name || item.trackingNumber || item.orderNumber || item.id,
    })),
    nextCursor,
  };
});

// ReadResource Handler
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const uri = request.params.uri;
  const match = uri.match(/^trackmage:\/\/\/(\w+)\/(.+)$/);
  if (!match) throw new Error('Invalid URI format');
  const [, type, id] = match;
  const resource = await client.getResource(type, id);
  return {
    contents: [{ uri, mimeType: 'application/json', text: JSON.stringify(resource) }],
  };
});

// Tools Definition
const tools = [
  {
    name: 'create_shipment',
    description: 'Create a new shipment',
    inputSchema: {
      type: 'object',
      properties: {
        workspaceId: { type: 'string', description: 'Workspace ID (optional, uses default from .env)' },
        trackingNumber: { type: 'string', description: 'Tracking number' },
        originCarrier: { type: 'string', description: 'Carrier code' },
        email: { type: 'string', description: 'Customer email' },
      },
      required: ['trackingNumber'],
    },
  },
  {
    name: 'create_order',
    description: 'Create a new order',
    inputSchema: {
      type: 'object',
      properties: {
        workspaceId: { type: 'string', description: 'Workspace ID (optional, uses default from .env)' },
        orderNumber: { type: 'string', description: 'Order number' },
        email: { type: 'string', description: 'Customer email' },
      },
      required: ['orderNumber'],
    },
  },
  {
    name: 'get_shipment_checkpoints',
    description: 'Get tracking checkpoints for a shipment',
    inputSchema: {
      type: 'object',
      properties: { shipmentId: { type: 'string', description: 'Shipment ID' } },
      required: ['shipmentId'],
    },
  },
  {
    name: 'list_orders',
    description: 'List orders from a workspace',
    inputSchema: {
      type: 'object',
      properties: {
        workspaceId: { type: 'string', description: 'Workspace ID (optional, uses default from .env)' },
        page: { type: 'number', description: 'Page number (default: 1)' },
        itemsPerPage: { type: 'number', description: 'Items per page (default: 30)' },
      },
      required: [],
    },
  },
  {
    name: 'list_shipments',
    description: 'List shipments from a workspace',
    inputSchema: {
      type: 'object',
      properties: {
        workspaceId: { type: 'string', description: 'Workspace ID (optional, uses default from .env)' },
        page: { type: 'number', description: 'Page number (default: 1)' },
        itemsPerPage: { type: 'number', description: 'Items per page (default: 30)' },
      },
      required: [],
    },
  },
  {
    name: 'list_carriers',
    description: 'List available carriers',
    inputSchema: {
      type: 'object',
      properties: {
        page: { type: 'number', description: 'Page number (default: 1)' },
        itemsPerPage: { type: 'number', description: 'Items per page (default: 30)' },
      },
      required: [],
    },
  },
  {
    name: 'update_order',
    description: 'Update an existing order',
    inputSchema: {
      type: 'object',
      properties: {
        orderId: { type: 'string', description: 'Order ID' },
        orderNumber: { type: 'string', description: 'Order number' },
        email: { type: 'string', description: 'Customer email' },
        status: { type: 'string', description: 'Order status' },
      },
      required: ['orderId'],
    },
  },
  {
    name: 'update_shipment',
    description: 'Update an existing shipment',
    inputSchema: {
      type: 'object',
      properties: {
        shipmentId: { type: 'string', description: 'Shipment ID' },
        trackingNumber: { type: 'string', description: 'Tracking number' },
        originCarrier: { type: 'string', description: 'Carrier code' },
        email: { type: 'string', description: 'Customer email' },
        status: { type: 'string', description: 'Shipment status' },
      },
      required: ['shipmentId'],
    },
  },
  {
    name: 'detect_carrier',
    description: 'Detect possible carriers for a tracking number',
    inputSchema: {
      type: 'object',
      properties: {
        trackingNumber: { type: 'string', description: 'Tracking number to detect carrier for' },
      },
      required: ['trackingNumber'],
    },
  },
  {
    name: 'retrack_shipments',
    description: 'Retrack multiple shipments by tracking numbers',
    inputSchema: {
      type: 'object',
      properties: {
        workspaceId: { type: 'string', description: 'Workspace ID (optional, uses default from .env)' },
        trackingNumbers: {
          type: 'array',
          description: 'Array of tracking number objects',
          items: {
            type: 'object',
            properties: {
              number: { type: 'string', description: 'Tracking number' },
              originCarrier: { type: 'string', description: 'Optional carrier code override' },
            },
            required: ['number'],
          },
        },
      },
      required: ['trackingNumbers'],
    },
  },
];

// ListTools Handler
server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools }));

// CallTool Handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    switch (name) {
      case 'create_shipment':
        const shipment = await client.createShipment(args.workspaceId || TRACKMAGE_WORKSPACE_ID, args);
        return { content: [{ type: 'text', text: `Shipment created: ${shipment.id}` }], isError: false };
      case 'create_order':
        const order = await client.createOrder(args.workspaceId || TRACKMAGE_WORKSPACE_ID, args);
        return { content: [{ type: 'text', text: `Order created: ${order.id}` }], isError: false };
      case 'get_shipment_checkpoints':
        const checkpoints = await client.getCheckpoints(args.shipmentId);
        return { content: [{ type: 'text', text: JSON.stringify(checkpoints, null, 2) }], isError: false };
      case 'list_orders':
        const ordersResult = await client.listResources('orders', {
          workspaceId: args.workspaceId || TRACKMAGE_WORKSPACE_ID,
          page: args.page || 1,
          itemsPerPage: args.itemsPerPage || 30,
        });
        return { content: [{ type: 'text', text: JSON.stringify(ordersResult.items, null, 2) }], isError: false };
      case 'list_shipments':
        const shipmentsResult = await client.listResources('shipments', {
          workspaceId: args.workspaceId || TRACKMAGE_WORKSPACE_ID,
          page: args.page || 1,
          itemsPerPage: args.itemsPerPage || 30,
        });
        return { content: [{ type: 'text', text: JSON.stringify(shipmentsResult.items, null, 2) }], isError: false };
      case 'list_carriers':
        const carriersResult = await client.listResources('carriers', {
          page: args.page || 1,
          itemsPerPage: args.itemsPerPage || 30,
        });
        return { content: [{ type: 'text', text: JSON.stringify(carriersResult.items, null, 2) }], isError: false };
      case 'update_order':
        const { orderId, ...orderUpdateData } = args;
        const updatedOrder = await client.updateOrder(orderId, orderUpdateData);
        return { content: [{ type: 'text', text: `Order updated: ${updatedOrder.id}` }], isError: false };
      case 'update_shipment':
        const { shipmentId, ...shipmentUpdateData } = args;
        const updatedShipment = await client.updateShipment(shipmentId, shipmentUpdateData);
        return { content: [{ type: 'text', text: `Shipment updated: ${updatedShipment.id}` }], isError: false };
      case 'detect_carrier':
        const carrierDetection = await client.detectCarrier(args.trackingNumber);
        return { content: [{ type: 'text', text: JSON.stringify(carrierDetection, null, 2) }], isError: false };
      case 'retrack_shipments':
        const retrackResult = await client.retrackShipments(
          args.workspaceId || TRACKMAGE_WORKSPACE_ID,
          args.trackingNumbers
        );
        return { content: [{ type: 'text', text: JSON.stringify(retrackResult, null, 2) }], isError: false };
      default:
        throw new Error('Unknown tool: ' + name);
    }
  } catch (error) {
    return { content: [{ type: 'text', text: `Error: ${error.message}` }], isError: true };
  }
});

// Start Server
async function startServer() {
  try {
    await client.refreshToken(); // Initial token fetch to verify credentials
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.log('TrackMage MCP server started');
  } catch (error) {
    console.error('Failed to start server:', error.message);
    process.exit(1);
  }
}

startServer();
