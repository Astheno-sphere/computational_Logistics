'use strict';

function detectAuthBypass(endpointKey, authedStatus, anonymousStatus) {
  if ((authedStatus === 200 || authedStatus === 204) && anonymousStatus === 200) {
    return {
      endpoint: endpointKey,
      rootCause: 'auth_bypass',
      detail: `${endpointKey} returned 200 without auth`,
    };
  }
  return null;
}

module.exports = { detectAuthBypass };
