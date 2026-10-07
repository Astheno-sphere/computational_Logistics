/**
 * Port Utilities - Port availability checking and allocation
 *
 * Utilities for checking if a port is available and finding
 * an available port in a specified range.
 *
 * 关联文件：
 * - @extension/src/services/backendManager.ts - 后端管理器使用此工具动态分配端口
 */

import * as net from 'net';

const MIN_PORT = 8001;
const MAX_PORT = 9000;
const MAX_RETRIES = 50;

/**
 * Check if a port is available on the specified host
 */
export function isPortAvailable(port: number, host: string = '127.0.0.1'): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();

    server.once('error', (err: NodeJS.ErrnoException) => {
      if (err.code === 'EADDRINUSE' || err.code === 'EACCES') {
        resolve(false);
      } else {
        // Other errors might mean the port is not available
        resolve(false);
      }
    });

    server.once('listening', () => {
      server.close();
      resolve(true);
    });

    server.listen(port, host);
  });
}

/**
 * Find an available port, starting from a random port in the range
 */
export async function findAvailablePort(
  minPort: number = MIN_PORT,
  maxPort: number = MAX_PORT
): Promise<number> {
  // Generate a random starting port within the range
  const range = maxPort - minPort + 1;
  const startPort = minPort + Math.floor(Math.random() * range);

  for (let i = 0; i < Math.min(range, MAX_RETRIES); i++) {
    const port = minPort + ((startPort + i - minPort) % range);
    if (await isPortAvailable(port)) {
      return port;
    }
  }

  throw new Error(`No available port found in range ${minPort}-${maxPort}`);
}

/**
 * Find an available port starting from a specific port
 */
export async function findAvailablePortFrom(
  startPort: number,
  maxPort: number = MAX_PORT
): Promise<number> {
  for (let port = startPort; port <= maxPort; port++) {
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  throw new Error(`No available port found from ${startPort} to ${maxPort}`);
}
