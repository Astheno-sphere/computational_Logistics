'use strict';

const fs = require('fs');
const path = require('path');
const { getOutputDir, ensureDir, readJson, writeJson } = require('../cache');

function snapshotSchemas(probeResults, config) {
  const dir = getSchemaHistoryDir(config);
  ensureDir(dir);
  const current = {};
  for (const [endpointKey, result] of Object.entries(probeResults || {})) {
    if (result && result.responseShape && !isEmptyShapeSample(result)) {
      current[endpointKey] = result.responseShape;
    }
  }

  const previous = loadPreviousSchemaSnapshot(config);
  const drift = diffSchemaSnapshots(previous ? previous.schemas : null, current);
  const file = path.join(dir, `schemas-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
  writeJson(file, { generatedAt: new Date().toISOString(), schemas: current, drift });
  return drift;
}

function loadPreviousSchemaSnapshot(config) {
  const dir = getSchemaHistoryDir(config);
  if (!fs.existsSync(dir)) return null;
  const files = fs.readdirSync(dir)
    .filter(f => f.startsWith('schemas-') && f.endsWith('.json'))
    .sort()
    .reverse();
  return files.length > 0 ? readJson(path.join(dir, files[0])) : null;
}

function diffSchemaSnapshots(previous, current) {
  if (!previous) return [];
  const changes = [];
  for (const [endpointKey, shape] of Object.entries(current || {})) {
    const oldShape = previous[endpointKey];
    if (!oldShape) continue;
    if (oldShape.type && shape.type && oldShape.type !== shape.type) {
      const kind = isNullableTypeChange(oldShape.type, shape.type) ? 'sample_variation' : 'breaking';
      changes.push({
        endpoint: endpointKey,
        field: '$body',
        kind,
        detail: `Top-level response type changed: ${oldShape.type} -> ${shape.type}`,
      });
    }
    for (const [field, type] of Object.entries(shape.fields || {})) {
      if (!oldShape.fields || !(field in oldShape.fields)) {
        changes.push({ endpoint: endpointKey, field, kind: 'additive', detail: `New field ${field}` });
      } else if (oldShape.fields[field] !== type) {
        const kind = isNullableTypeChange(oldShape.fields[field], type) ? 'sample_variation' : 'breaking';
        changes.push({
          endpoint: endpointKey,
          field,
          kind,
          detail: `Type changed for ${field}: ${oldShape.fields[field]} -> ${type}`,
        });
      }
    }
    for (const field of Object.keys(oldShape.fields || {})) {
      if (!shape.fields || !(field in shape.fields)) {
        changes.push({ endpoint: endpointKey, field, kind: 'breaking', detail: `Removed field ${field}` });
      }
    }
  }
  return changes;
}

function isEmptyShapeSample(result) {
  if (!result.empty) return false;
  const fields = result.responseShape && result.responseShape.fields;
  return !fields || Object.keys(fields).length === 0;
}

function isNullableTypeChange(before, after) {
  return before === 'null' || after === 'null';
}

function inferShape(body) {
  const sample = Array.isArray(body) ? body[0] : body;
  if (!sample || typeof sample !== 'object') {
    return { type: Array.isArray(body) ? 'array' : typeof body, fields: {} };
  }
  const fields = {};
  for (const [key, value] of Object.entries(sample)) {
    fields[key] = Array.isArray(value) ? 'array' : value === null ? 'null' : typeof value;
  }
  return { type: Array.isArray(body) ? 'array' : 'object', fields };
}

function getSchemaHistoryDir(config) {
  return path.join(getOutputDir(config), 'history', 'schemas');
}

module.exports = { snapshotSchemas, loadPreviousSchemaSnapshot, diffSchemaSnapshots, inferShape };
