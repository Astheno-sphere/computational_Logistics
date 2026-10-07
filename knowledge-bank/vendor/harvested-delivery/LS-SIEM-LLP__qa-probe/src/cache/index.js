'use strict';

const fs = require('fs');
const path = require('path');

function getOutputDir(config) {
  return path.resolve(process.cwd(), config.output.dir);
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

function readJson(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

async function saveGraph(graph, config) {
  const dir = getOutputDir(config);
  ensureDir(dir);
  writeJson(path.join(dir, 'graph.json'), graph);
}

async function loadGraph(config) {
  const dir = getOutputDir(config);
  return readJson(path.join(dir, 'graph.json'));
}

async function saveProbeResults(results, config) {
  const dir = getOutputDir(config);
  ensureDir(dir);
  writeJson(path.join(dir, 'probe-results.json'), results);
}

async function loadProbeResults(config) {
  const dir = getOutputDir(config);
  return readJson(path.join(dir, 'probe-results.json'));
}

async function saveReport(report, config) {
  const dir = getOutputDir(config);
  ensureDir(dir);
  writeJson(path.join(dir, 'report.json'), report);
}

async function loadReport(config) {
  const dir = getOutputDir(config);
  return readJson(path.join(dir, 'report.json'));
}

module.exports = {
  getOutputDir,
  saveGraph,
  loadGraph,
  saveProbeResults,
  loadProbeResults,
  saveReport,
  loadReport,
  writeJson,
  readJson,
  ensureDir,
};
