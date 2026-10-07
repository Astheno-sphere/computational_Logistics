'use strict';

function getRepairProvider(name, config) {
  if (name === 'openai') return require('./openai').createProvider(config);
  if (name === 'anthropic') return require('./anthropic').createProvider(config);
  if (name === 'ollama') return require('./ollama').createProvider(config);
  return createProvider(config);
}

function createProvider() {
  return { name: 'disabled', repair: () => null };
}

module.exports = { createProvider, getRepairProvider };
