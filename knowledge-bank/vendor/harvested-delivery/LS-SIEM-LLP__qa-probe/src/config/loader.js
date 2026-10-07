'use strict';

const path = require('path');
const fs = require('fs');
const { ConfigSchema } = require('./schema');

function loadConfig(configPath) {
  const resolved = path.resolve(process.cwd(), configPath);

  if (!fs.existsSync(resolved)) {
    throw new Error(
      `Config file not found: ${resolved}\n` +
      `Create qa-probe.config.js in your project root, or use --config to point to one.\n` +
      `See examples/ for starter configs.`
    );
  }

  let raw;
  try {
    raw = require(resolved);
  } catch (err) {
    throw new Error(`Failed to load config at ${resolved}:\n${err.message}`);
  }

  // Support default export and function configs
  if (typeof raw === 'function') {
    raw = raw();
  }
  if (raw && raw.default) {
    raw = raw.default;
  }

  const result = ConfigSchema.safeParse(raw);
  if (!result.success) {
    const issues = result.error.issues
      .map(i => `  • ${i.path.join('.')}: ${i.message}`)
      .join('\n');
    throw new Error(`Config validation errors in ${resolved}:\n${issues}`);
  }

  return result.data;
}

module.exports = { loadConfig };
