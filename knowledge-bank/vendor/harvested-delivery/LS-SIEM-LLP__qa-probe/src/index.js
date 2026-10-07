'use strict';

// Public API for programmatic use
module.exports = {
  analyze: require('./analyze'),
  probe: require('./probe'),
  report: require('./report'),
  config: require('./config/loader'),
  cache: require('./cache'),
};
