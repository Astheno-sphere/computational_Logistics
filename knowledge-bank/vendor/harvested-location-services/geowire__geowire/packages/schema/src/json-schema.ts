import { z } from "zod";
import { Place } from "./place.js";
import { ProviderManifest } from "./manifest.js";
import {
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
  GetPlaceRequest,
  AutocompleteRequest,
} from "./requests.js";
import { SearchPlacesResponse } from "./response.js";

/**
 * Zod 스키마 → JSON Schema 생성.
 * `specs/` 디렉터리의 공개 스펙 파일과 CI에서 diff 검사해
 * 스펙과 구현의 불일치를 차단한다 (설계 §4.2).
 */
export function generateJsonSchemas(): Record<string, unknown> {
  return {
    "place/v1": z.toJSONSchema(Place),
    "provider-manifest/v1": z.toJSONSchema(ProviderManifest),
    "requests/search-places": z.toJSONSchema(SearchPlacesRequest),
    "requests/geocode": z.toJSONSchema(GeocodeRequest),
    "requests/reverse-geocode": z.toJSONSchema(ReverseGeocodeRequest),
    "requests/get-place": z.toJSONSchema(GetPlaceRequest),
    "requests/autocomplete": z.toJSONSchema(AutocompleteRequest),
    "responses/search-places": z.toJSONSchema(SearchPlacesResponse),
  };
}
