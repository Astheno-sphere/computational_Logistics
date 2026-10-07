/**
 * Host / URL checks shared by skill-source parsing and install guards.
 */

function isPrivateOrLocalHostname(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, '');
  if (!host || host === 'localhost' || host.endsWith('.localhost') || host === 'metadata.google.internal') {
    return true;
  }
  if (host === '::1' || host === '0.0.0.0') {
    return true;
  }
  const ipv4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (ipv4) {
    const octets = ipv4.slice(1).map((part) => Number(part));
    if (octets.some((n) => n > 255)) {
      return true;
    }
    const [a, b] = octets;
    if (a === 10 || a === 127 || a === 0) {
      return true;
    }
    if (a === 169 && b === 254) {
      return true;
    }
    if (a === 192 && b === 168) {
      return true;
    }
    if (a === 172 && b >= 16 && b <= 31) {
      return true;
    }
  }
  if (host.startsWith('fc') || host.startsWith('fd') || host.startsWith('fe80:')) {
    return true;
  }
  return false;
}

/**
 * Accept only https origins that are not localhost / link-local / RFC1918 literals.
 */
export function isAllowedSkillSourceBaseUrl(baseUrl: string): boolean {
  try {
    const parsed = new URL(baseUrl.trim());
    if (parsed.protocol !== 'https:') {
      return false;
    }
    if (parsed.username || parsed.password) {
      return false;
    }
    if (isPrivateOrLocalHostname(parsed.hostname)) {
      return false;
    }
    return Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

export function isPrivateOrLocalHost(hostname: string): boolean {
  return isPrivateOrLocalHostname(hostname);
}
