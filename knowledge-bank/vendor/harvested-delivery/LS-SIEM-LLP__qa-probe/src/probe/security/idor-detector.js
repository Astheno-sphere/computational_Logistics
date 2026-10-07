'use strict';

function buildIdorProbePaths(pathPattern, ids = ['1', '2', '9999']) {
  return ids.map(id => pathPattern.replace(/\{[^}]+\}/g, id));
}

function detectIdorAccess(responses) {
  return (responses || [])
    .filter(item => item.ownerPersona && item.persona !== item.ownerPersona && item.status === 200)
    .map(item => ({
      rootCause: 'privilege_escalation',
      endpoint: item.endpoint,
      persona: item.persona,
      ownerPersona: item.ownerPersona,
    }));
}

module.exports = { buildIdorProbePaths, detectIdorAccess };
