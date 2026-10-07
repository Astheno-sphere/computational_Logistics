'use strict';

function createProvider() {
  return { name: 'ollama', repair: () => null };
}

module.exports = { createProvider };
