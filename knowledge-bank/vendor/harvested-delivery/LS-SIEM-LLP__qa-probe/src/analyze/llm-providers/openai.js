'use strict';

function createProvider() {
  return { name: 'openai', repair: () => null };
}

module.exports = { createProvider };
