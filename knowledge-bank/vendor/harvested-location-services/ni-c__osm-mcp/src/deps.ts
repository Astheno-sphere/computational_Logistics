import type { Config } from './config.js';
import type { NominatimBackend } from './backends/nominatim.js';
import type { OrsBackend } from './backends/ors.js';
import type { OsrmBackend } from './backends/osrm.js';
import type { OverpassBackend } from './backends/overpass.js';
import type { ValhallaBackend } from './backends/valhalla.js';
import type { PlaceResolver } from './resolve.js';

/** Everything the tool registrars need, wired once in server.ts. */
export interface Deps {
  config: Config;
  resolver: PlaceResolver;
  nominatim: NominatimBackend;
  osrm: OsrmBackend;
  overpass: OverpassBackend;
  valhalla: ValhallaBackend;
  ors: OrsBackend;
}
