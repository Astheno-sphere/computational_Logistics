'use strict';

function createProvider() {
  return { name: 'anthropic', repair: () => null };
}

module.exports = { createProvider };
