'use strict';

const fs = require('fs');
const path = require('path');
const { getOutputDir, ensureDir, writeJson, readJson } = require('./index');

function getHistoryDir(config) {
  return path.join(getOutputDir(config), 'history');
}

/**
 * Save the current report to history with a timestamp key.
 * Prunes old history entries to stay within keepHistory limit.
 */
function saveToHistory(report, config) {
  const histDir = getHistoryDir(config);
  ensureDir(histDir);

  const timestamp = `${new Date().toISOString().replace(/[:.]/g, '-')}-${process.hrtime.bigint()}`;
  const file = path.join(histDir, `run-${timestamp}.json`);
  writeJson(file, report);

  pruneHistory(histDir, config.output.keepHistory || 30);
}

function pruneHistory(histDir, keepCount) {
  const files = fs.readdirSync(histDir)
    .filter(f => f.endsWith('.json'))
    .sort()
    .reverse(); // newest first

  const toDelete = files.slice(keepCount);
  for (const f of toDelete) {
    fs.unlinkSync(path.join(histDir, f));
  }
}

/**
 * Load the previous run's report (the one just before the current).
 */
function loadPreviousRun(config) {
  const histDir = getHistoryDir(config);
  if (!fs.existsSync(histDir)) return null;

  const files = fs.readdirSync(histDir)
    .filter(f => f.endsWith('.json'))
    .sort()
    .reverse();

  if (files.length === 0) return null;
  return readJson(path.join(histDir, files[0]));
}

function loadRecentRuns(config, limit = 30) {
  const histDir = getHistoryDir(config);
  if (!fs.existsSync(histDir)) return [];
  return fs.readdirSync(histDir)
    .filter(f => f.endsWith('.json'))
    .sort()
    .reverse()
    .slice(0, limit)
    .map(f => readJson(path.join(histDir, f)))
    .filter(Boolean)
    .reverse();
}

module.exports = { saveToHistory, loadPreviousRun, loadRecentRuns, pruneHistory };
