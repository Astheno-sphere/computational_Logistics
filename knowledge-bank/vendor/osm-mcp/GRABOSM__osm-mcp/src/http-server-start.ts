#!/usr/bin/env node

import 'dotenv/config';
import OpenStreetMapHTTPServer from './http-server.js';

// Get port from environment variable or default to 8888
const port = parseInt(process.env.PORT || '8888', 10);

// Create and start the HTTP server
const server = new OpenStreetMapHTTPServer(port);
server.start();

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down HTTP server...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n🛑 Shutting down HTTP server...');
  process.exit(0);
}); 