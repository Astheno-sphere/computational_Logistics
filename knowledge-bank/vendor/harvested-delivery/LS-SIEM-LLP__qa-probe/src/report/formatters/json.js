'use strict';

const { writeJson } = require('../../cache');
const path = require('path');

function writeJsonReport(report, config) {
  const outPath = path.join(process.cwd(), config.output.dir, 'report.json');
  writeJson(outPath, report);
  return outPath;
}

module.exports = { writeJsonReport };
