"""
Name Standardizer Module
Matches and standardizes place names against canonical geometry datasets.

The geometry files are the source of truth for names:
- geometry/global/exact/admin_0.parquet - countries (admin_0)
- {ISO3}.parquet - per-country admin levels

This module:
1. Loads canonical names from geometry files
2. Builds alias mappings from conversions.json
3. Matches incoming names to canonical names
4. Provides loc_id lookups from names and codes (FIPS, ISO)
5. Logs mismatches to the hosted control plane for data quality tracking
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import re
import unicodedata
from rapidfuzz import fuzz, process

from .duckdb_helpers import duckdb_available, select_columns_from_parquet
from .foundation_helpers import load_global_countries_frame, load_reference_json
from .paths import GEOMETRY_DIR


class NameStandardizer:
    """Standardizes place names to match canonical geometry datasets."""

    def __init__(self, data_dir: Path = None):
        """
        Initialize the name standardizer.

        Args:
            data_dir: Path to data_pipeline directory. Defaults to script's parent.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent

        self.data_dir = data_dir
        self.geom_dir = GEOMETRY_DIR
        self.conversions_path = data_dir / "conversions.json"

        # Canonical name lookups (populated on first use)
        self._country_names: Dict[str, str] = {}  # lowercase -> canonical
        self._country_codes: Dict[str, str] = {}  # code -> canonical name
        self._place_names: Dict[str, str] = {}    # lowercase -> canonical
        self._us_place_names: Dict[str, str] = {} # lowercase -> canonical

        # Alias mappings from conversions.json
        self._aliases: Dict[str, str] = {}  # alias lowercase -> canonical
        # Reverse index over every name universe we know: common names from
        # iso_codes.json and formal names from Admin0 Full both point at the
        # ISO3. Without this, a country whose geometry name is formal ("the
        # Federal Republic of Germany") cannot be found by its common name.
        self._name_to_code: Dict[str, str] = {}  # normalized name -> ISO3
        self._country_name_index: Dict[Tuple[str, Optional[int]], Dict[str, str]] = {}

        # Known aggregates (to skip logging as mismatches)
        self._aggregate_names: Set[str] = set()  # lowercase aggregate names

        # Track what's been loaded
        self._loaded = False

        # Mismatched names for logging
        self.mismatches: List[Dict] = []

    def _load_data(self):
        """Load canonical names and aliases on first use."""
        if self._loaded:
            return

        # Load conversions.json for aliases
        if self.conversions_path.exists():
            with open(self.conversions_path, 'r', encoding='utf-8') as f:
                conv = json.load(f)

            # Load ISO codes from reference/iso_codes.json
            iso_data = load_reference_json("iso_codes.json")
            iso3_to_name = iso_data.get('iso3_to_name', {}) if isinstance(iso_data, dict) else {}

            # Build alias map from iso_codes.json
            for code, name in iso3_to_name.items():
                self._country_codes[code] = name
                self._aliases[self._normalize_lookup_text(name)] = name
                self._aliases[self._normalize_lookup_text(code)] = name
                self._name_to_code[self._normalize_lookup_text(name)] = code
                self._name_to_code[self._normalize_lookup_text(code)] = code

            # Load aggregate names from regional_groupings and region_aliases
            # These are entities like "African Region", "Europe", etc. that will be removed
            for group_name in conv.get('regional_groupings', {}).keys():
                # Convert underscore names to readable format
                readable_name = group_name.replace('_', ' ').lower()
                self._aggregate_names.add(self._normalize_lookup_text(readable_name))
                self._aggregate_names.add(self._normalize_lookup_text(group_name))
            for alias in conv.get('region_aliases', {}).keys():
                self._aggregate_names.add(self._normalize_lookup_text(alias))

            # Add common aggregate patterns
            self._aggregate_names.update({
                'world', 'global', 'international',
                'africa', 'asia', 'europe', 'north america', 'south america',
                'oceania', 'antarctica', 'australia and new zealand',
                'african region', 'eastern mediterranean region', 'european region',
                'region of the americas', 'south-east asia region', 'western pacific region',
                'high income', 'upper middle income', 'lower middle income', 'low income',
            })

            # Add common aliases
            self._add_common_aliases()

        # Load current runtime country geometry inventory.
        df = load_global_countries_frame()
        if df is not None:
            for _, row in df.iterrows():
                name = row.get('name')
                code = row.get('loc_id') or row.get('code')
                abbrev = row.get('abbrev')

                if pd.notna(name):
                    name_str = str(name).strip()
                    code_str = str(code).strip().upper() if pd.notna(code) else ""
                    if len(code_str) == 3 and code_str.isalpha():
                        self._country_names[self._normalize_lookup_text(name_str)] = name_str
                        self._country_codes[code_str] = name_str
                        self._aliases[self._normalize_lookup_text(code_str)] = name_str
                        # Formal geometry name and code both resolve to the code.
                        self._name_to_code[self._normalize_lookup_text(name_str)] = code_str
                        self._name_to_code[self._normalize_lookup_text(code_str)] = code_str
                    if pd.notna(abbrev) and abbrev != name:
                        self._aliases[self._normalize_lookup_text(abbrev)] = name
                        if len(code_str) == 3 and code_str.isalpha():
                            self._name_to_code.setdefault(self._normalize_lookup_text(abbrev), code_str)

        # Optional older geometry extracts for point/city aliases.
        places_path = self.geom_dir / "places_geometry.csv"
        if places_path.exists():
            df = pd.read_csv(places_path)
            for _, row in df.iterrows():
                name = row.get('name')
                if pd.notna(name):
                    self._place_names[self._normalize_lookup_text(name)] = name

        # Load usplaces_geometry.csv
        usplaces_path = self.geom_dir / "usplaces_geometry.csv"
        if usplaces_path.exists():
            df = pd.read_csv(usplaces_path)
            for _, row in df.iterrows():
                name = row.get('name')
                if pd.notna(name):
                    self._us_place_names[self._normalize_lookup_text(name)] = name

        self._loaded = True
        print(f"[NameStandardizer] Loaded {len(self._country_names)} countries, "
              f"{len(self._place_names)} places, {len(self._us_place_names)} US places, "
              f"{len(self._aliases)} aliases")

    def _add_common_aliases(self):
        """Add common name variants that map to canonical names."""
        # These are common variations found in datasets
        common_aliases = {
            # United States variants
            "united states of america": "United States",
            "usa": "United States",
            "u.s.": "United States",
            "u.s.a.": "United States",
            "us": "United States",
            "america": "United States",

            # United Kingdom variants
            "united kingdom of great britain and northern ireland": "United Kingdom",
            "uk": "United Kingdom",
            "u.k.": "United Kingdom",
            "great britain": "United Kingdom",
            "britain": "United Kingdom",
            "england": "United Kingdom",  # Often used interchangeably in datasets

            # United Arab Emirates variants
            # "uae" is what people actually write; the bare ISO3 code "are" is
            # deliberately not a natural-language match (see _SPAN_STOP_WORDS
            # in preprocessor_locations.py).
            "uae": "United Arab Emirates",
            "u.a.e.": "United Arab Emirates",
            "emirates": "United Arab Emirates",

            # Russia variants
            "russian federation": "Russia",

            # South Korea variants
            "republic of korea": "South Korea",
            "korea, south": "South Korea",
            "korea, republic of": "South Korea",
            "korea": "South Korea",  # Usually means South Korea in data

            # North Korea variants
            "democratic people's republic of korea": "North Korea",
            "korea, north": "North Korea",
            "korea, dem. people's rep.": "North Korea",

            # Iran variants
            "iran, islamic republic of": "Iran",
            "islamic republic of iran": "Iran",

            # Vietnam variants
            "viet nam": "Vietnam",

            # Ivory Coast variants
            "cote d'ivoire": "Ivory Coast",
            "cote divoire": "Ivory Coast",

            # DR Congo variants
            "congo, democratic republic of the": "Democratic Republic of the Congo",
            "congo, dem. rep.": "Democratic Republic of the Congo",
            "dem. rep. congo": "Democratic Republic of the Congo",
            "drc": "Democratic Republic of the Congo",
            "zaire": "Democratic Republic of the Congo",

            # Congo variants
            "congo, republic of the": "Congo",
            "republic of the congo": "Congo",
            "congo-brazzaville": "Congo",

            # Tanzania variants
            "tanzania, united republic of": "Tanzania",

            # Venezuela variants
            "venezuela, bolivarian republic of": "Venezuela",
            "venezuela (bolivarian republic of)": "Venezuela",

            # Bolivia variants
            "bolivia, plurinational state of": "Bolivia",
            "bolivia (plurinational state of)": "Bolivia",

            # Syria variants
            "syrian arab republic": "Syria",

            # Laos variants
            "lao people's democratic republic": "Laos",
            "lao pdr": "Laos",

            # Moldova variants
            "moldova, republic of": "Moldova",

            # Czechia variants
            "czech republic": "Czechia",

            # Eswatini variants
            "swaziland": "Eswatini",

            # North Macedonia variants
            "macedonia": "North Macedonia",
            "former yugoslav republic of macedonia": "North Macedonia",
            "fyrom": "North Macedonia",

            # Myanmar variants
            "burma": "Myanmar",

            # Cabo Verde variants
            "cape verde": "Cabo Verde",

            # Timor-Leste variants
            "east timor": "Timor-Leste",

            # Micronesia variants
            "micronesia, federated states of": "Micronesia",
            "micronesia (federated states of)": "Micronesia",
            "federated states of micronesia": "Micronesia",

            # Palestine variants
            "palestinian territories": "Palestine",
            "west bank and gaza": "Palestine",
            "occupied palestinian territory": "Palestine",

            # Taiwan variants
            "taiwan, province of china": "Taiwan",
            "chinese taipei": "Taiwan",

            # Hong Kong variants
            "hong kong sar": "Hong Kong",
            "hong kong, china": "Hong Kong",

            # Macau variants
            "macao": "Macau",
            "macau sar": "Macau",
            "macao, china": "Macau",

            # Vatican variants
            "holy see": "Vatican City",
            "vatican": "Vatican City",

            # Brunei variants
            "brunei darussalam": "Brunei",

            # WHO-specific naming conventions
            "iran (islamic republic of)": "Iran",
            "netherlands (kingdom of the)": "Netherlands",
            "republic of moldova": "Moldova",
            "united republic of tanzania": "Tanzania",
            "china, hong kong sar": "Hong Kong",
            "china, macao sar": "Macau",
            "occupied palestinian territory, including east jerusalem": "Palestine",
            "turkiye": "Turkey",
            "t\u00fcrkiye": "Turkey",  # Turkish spelling with umlaut
        }

        for alias, canonical in common_aliases.items():
            self._aliases[self._normalize_lookup_text(alias)] = canonical

    @staticmethod
    def _normalize_lookup_text(value: str) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.replace("&", " and ")
        text = re.sub(r"[^\w\s]+", " ", text)
        text = " ".join(text.split())
        return text

    def standardize_country_name(self, name: str, log_mismatch: bool = True) -> Tuple[str, bool]:
        """
        Standardize a country name to match canonical geometry.

        Args:
            name: Input country name
            log_mismatch: Whether to log names that don't match

        Returns:
            Tuple of (standardized_name, was_exact_match)
        """
        self._load_data()

        if pd.isna(name) or str(name).strip() == '':
            return name, False

        name_str = str(name).strip()
        name_lower = self._normalize_lookup_text(name_str)

        # 1. Check exact match in canonical names
        if name_lower in self._country_names:
            return self._country_names[name_lower], True

        # 2. Check aliases
        if name_lower in self._aliases:
            return self._aliases[name_lower], True

        # 3. Check if it's a code
        name_upper = name_str.upper()
        if name_upper in self._country_codes:
            return self._country_codes[name_upper], True

        # 4. Fuzzy match (last resort)
        canonical_names = list(self._country_names.values())
        if canonical_names:
            match = process.extractOne(name_str, canonical_names, scorer=fuzz.ratio)
            if match and match[1] >= 85:  # 85% similarity threshold
                if log_mismatch:
                    self.mismatches.append({
                        'original': name_str,
                        'matched': match[0],
                        'score': match[1],
                        'type': 'fuzzy_country'
                    })
                return match[0], False

        # 5. No match found - but skip logging if it's a known aggregate
        # (aggregates will be removed later by remove_aggregate_rows)
        if log_mismatch and name_lower not in self._aggregate_names:
            self.mismatches.append({
                'original': name_str,
                'matched': None,
                'score': 0,
                'type': 'no_match_country'
            })

        return name_str, False  # Return original if no match

    def standardize_country_column(self, df: pd.DataFrame, column: str) -> pd.DataFrame:
        """
        Standardize all country names in a DataFrame column.

        Args:
            df: DataFrame with country names
            column: Column name to standardize

        Returns:
            DataFrame with standardized names
        """
        self._load_data()

        if column not in df.columns:
            print(f"[NameStandardizer] Warning: Column '{column}' not found")
            return df

        df = df.copy()
        exact_matches = 0
        fuzzy_matches = 0
        no_matches = 0

        def standardize(name):
            nonlocal exact_matches, fuzzy_matches, no_matches
            std_name, exact = self.standardize_country_name(name, log_mismatch=True)
            if exact:
                exact_matches += 1
            elif std_name != name:
                fuzzy_matches += 1
            else:
                no_matches += 1
            return std_name

        df[column] = df[column].apply(standardize)

        print(f"[NameStandardizer] Standardized '{column}': "
              f"{exact_matches} exact, {fuzzy_matches} fuzzy, {no_matches} unmatched")

        return df

    def get_canonical_country_names(self) -> Set[str]:
        """Get set of all canonical country names."""
        self._load_data()
        return set(self._country_names.values())

    def get_country_code(self, name: str) -> Optional[str]:
        """Get ISO-3 code for a country name, common or formal."""
        self._load_data()

        # Direct hit on any known name universe: common name, formal geometry
        # name, abbreviation, or the code itself.
        direct = self._name_to_code.get(self._normalize_lookup_text(name))
        if direct:
            return direct

        # Otherwise standardize first, then match on the canonical name. This
        # is what catches fuzzy matches.
        std_name, _ = self.standardize_country_name(name, log_mismatch=False)
        standardized = self._name_to_code.get(self._normalize_lookup_text(std_name))
        if standardized:
            return standardized

        for code, canon_name in self._country_codes.items():
            if canon_name == std_name:
                return code

        return None

    def validate_dataset_names(self, df: pd.DataFrame, name_column: str,
                               level: str = 'country') -> Dict:
        """
        Validate names in a dataset against canonical geometry.

        Args:
            df: DataFrame to validate
            name_column: Column containing place names
            level: Geographic level ('country', 'city', 'us_place')

        Returns:
            Dict with validation results
        """
        self._load_data()

        if name_column not in df.columns:
            return {'error': f"Column '{name_column}' not found"}

        # Get unique names
        unique_names = df[name_column].dropna().unique()

        # Get canonical names for this level
        if level == 'country':
            canonical = set(self._country_names.values())
        elif level == 'city':
            canonical = set(self._place_names.values())
        elif level == 'us_place':
            canonical = set(self._us_place_names.values())
        else:
            return {'error': f"Unknown level: {level}"}

        # Check each name
        matched = []
        unmatched = []

        for name in unique_names:
            name_lower = self._normalize_lookup_text(str(name))

            # Check canonical
            if level == 'country':
                if name_lower in self._country_names or name_lower in self._aliases:
                    matched.append(name)
                else:
                    unmatched.append(name)
            elif level == 'city':
                if name_lower in self._place_names:
                    matched.append(name)
                else:
                    unmatched.append(name)
            elif level == 'us_place':
                if name_lower in self._us_place_names:
                    matched.append(name)
                else:
                    unmatched.append(name)

        return {
            'total_unique': len(unique_names),
            'matched': len(matched),
            'unmatched': len(unmatched),
            'match_rate': len(matched) / len(unique_names) * 100 if unique_names.size > 0 else 0,
            'unmatched_names': unmatched[:20],  # First 20 for review
            'level': level
        }

    def get_mismatches(self) -> List[Dict]:
        """Get list of name mismatches found during standardization."""
        return self.mismatches

    def clear_mismatches(self):
        """Clear the mismatches list."""
        self.mismatches = []

    # =================================================================
    # loc_id lookup methods (new parquet-based system)
    # =================================================================

    def get_loc_id_from_name(
        self,
        name: str,
        country: str = None,
        admin_level: int = None
    ) -> Optional[str]:
        """
        Get loc_id for a place name.

        Args:
            name: Place name to look up
            country: ISO3 country code to narrow search (e.g., 'USA')
            admin_level: Admin level to search (0=country, 1=state, 2=county)

        Returns:
            loc_id or None if not found

        Examples:
            get_loc_id_from_name('California', 'USA') -> 'USA-CA'
            get_loc_id_from_name('United States') -> 'USA'
            get_loc_id_from_name('Los Angeles', 'USA', admin_level=2) -> 'USA-CA-037'
        """
        self._load_data()

        name_lower = self._normalize_lookup_text(name)

        # When a country hint is present, prefer that country's geometry spine
        # before falling back to a same-named sovereign country.
        if country:
            loc_id = self._lookup_in_parquet(name_lower, country, admin_level)
            if loc_id:
                return loc_id

        # Try country lookup.
        if admin_level is None or admin_level == 0:
            # Check canonical country names
            if name_lower in self._country_names:
                canon_name = self._country_names[name_lower]
                # Find ISO3 code
                for code, cname in self._country_codes.items():
                    if cname == canon_name:
                        return code
            # Check aliases
            if name_lower in self._aliases:
                canon_name = self._aliases[name_lower]
                for code, cname in self._country_codes.items():
                    if cname == canon_name:
                        return code

        return None

    def _lookup_in_parquet(
        self,
        name_lower: str,
        country: str,
        admin_level: int = None
    ) -> Optional[str]:
        """Look up a name in country parquet file."""
        cache_key = (str(country or "").upper(), admin_level)
        if cache_key not in self._country_name_index:
            parquet_file = GEOMETRY_DIR / f"{country}.parquet"
            if not parquet_file.exists():
                return None

            try:
                columns = ["loc_id", "name", "admin_level"]
                # Name resolution should prefer the local geometry spine directly.
                # Falling through cloud DuckDB here makes deterministic resolver QA
                # brittle and can fail even when the local geometry bank is healthy.
                if parquet_file.exists():
                    df = pd.read_parquet(parquet_file, columns=columns)
                elif duckdb_available():
                    df = select_columns_from_parquet(parquet_file, columns)
                else:
                    return None

                if admin_level is not None:
                    df = df[df["admin_level"] == admin_level]

                df["name_key"] = df["name"].astype(str).map(self._normalize_lookup_text)
                df = df[df["name_key"] != ""]
                index: Dict[str, Optional[str]] = {}
                for row in df.itertuples(index=False):
                    key = str(row.name_key or "").strip()
                    loc_id = str(row.loc_id or "").strip()
                    if not key or not loc_id:
                        continue
                    existing = index.get(key)
                    if existing is None and key in index:
                        continue
                    if existing and existing != loc_id:
                        index[key] = None
                        continue
                    if key not in index:
                        index[key] = loc_id
                self._country_name_index[cache_key] = index
            except Exception:
                self._country_name_index[cache_key] = {}

        resolved = self._country_name_index.get(cache_key, {}).get(name_lower)
        if isinstance(resolved, str) and resolved:
            return resolved
        return None

    def get_loc_id_from_fips(
        self,
        state_fips: str,
        county_fips: str = None
    ) -> Optional[str]:
        """
        Get loc_id from FIPS codes.

        Args:
            state_fips: 2-digit state FIPS code (e.g., '06' for California)
            county_fips: 3 or 5-digit county FIPS (e.g., '037' or '06037')

        Returns:
            loc_id or None

        Examples:
            get_loc_id_from_fips('06') -> 'USA-CA'
            get_loc_id_from_fips('06', '037') -> 'USA-CA-037'
            get_loc_id_from_fips('06', '06037') -> 'USA-CA-037'
        """
        # State FIPS to abbreviation mapping
        state_fips_to_abbrev = {
            '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA',
            '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL',
            '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN',
            '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME',
            '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS',
            '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
            '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
            '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
            '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
            '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI',
            '56': 'WY', '60': 'AS', '66': 'GU', '69': 'MP', '72': 'PR',
            '78': 'VI',
        }

        # Normalize state FIPS
        state_fips = str(state_fips).zfill(2)
        abbrev = state_fips_to_abbrev.get(state_fips)

        if not abbrev:
            return None

        if county_fips is None:
            return f"USA-{abbrev}"

        # Normalize county FIPS (can be 3-digit or 5-digit)
        county_fips = str(county_fips)
        if len(county_fips) == 5:
            county_code = county_fips[-3:]
        elif len(county_fips) == 3:
            county_code = county_fips
        else:
            county_code = county_fips[-3:]

        return f"USA-{abbrev}-{county_code.zfill(3)}"

    def get_loc_id_from_iso(self, iso_code: str) -> Optional[str]:
        """
        Get loc_id from ISO 3166 code.

        Args:
            iso_code: ISO 3166-1 (country) or ISO 3166-2 (subdivision) code
                      Examples: 'USA', 'US', 'US-CA', 'FR-IDF'

        Returns:
            loc_id or None

        Examples:
            get_loc_id_from_iso('USA') -> 'USA'
            get_loc_id_from_iso('US') -> 'USA'
            get_loc_id_from_iso('US-CA') -> 'USA-CA'
            get_loc_id_from_iso('FR-IDF') -> 'FRA-IDF'
        """
        self._load_data()

        iso_code = iso_code.upper().strip()

        # ISO 3166-2 (subdivision) - format: XX-YYY
        if '-' in iso_code:
            parts = iso_code.split('-')
            alpha2 = parts[0]
            subdivision = parts[1]

            # Convert alpha-2 to alpha-3
            alpha2_to_alpha3 = {
                'US': 'USA', 'GB': 'GBR', 'FR': 'FRA', 'DE': 'DEU', 'CA': 'CAN',
                'AU': 'AUS', 'JP': 'JPN', 'CN': 'CHN', 'IN': 'IND', 'BR': 'BRA',
                'MX': 'MEX', 'IT': 'ITA', 'ES': 'ESP', 'RU': 'RUS', 'KR': 'KOR',
                'ZA': 'ZAF', 'AR': 'ARG', 'TR': 'TUR', 'SA': 'SAU', 'ID': 'IDN',
            }
            alpha3 = alpha2_to_alpha3.get(alpha2, alpha2)

            # For 2-letter alpha2, try to expand
            if len(alpha3) == 2:
                for code, name in self._country_codes.items():
                    if len(code) == 3 and code[:2] == alpha3:
                        alpha3 = code
                        break

            return f"{alpha3}-{subdivision}"

        # ISO 3166-1 (country)
        if len(iso_code) == 3:
            # Already alpha-3
            if iso_code in self._country_codes:
                return iso_code
        elif len(iso_code) == 2:
            # Convert alpha-2 to alpha-3
            for code, name in self._country_codes.items():
                # Simple heuristic: check common mappings
                alpha2_map = {
                    'US': 'USA', 'GB': 'GBR', 'UK': 'GBR', 'FR': 'FRA',
                    'DE': 'DEU', 'CA': 'CAN', 'AU': 'AUS', 'JP': 'JPN',
                    'CN': 'CHN', 'IN': 'IND', 'BR': 'BRA', 'RU': 'RUS',
                }
                if iso_code in alpha2_map:
                    return alpha2_map[iso_code]

        return iso_code if iso_code in self._country_codes else None

    def log_mismatches_to_control_plane(self, dataset_filename: str = None):
        """
        Log name mismatches to the hosted control plane for data quality tracking.

        Deduplicates mismatches before logging - each unique name is logged once.

        Args:
            dataset_filename: Name of the dataset being processed
        """
        if not self.mismatches:
            return

        try:
            from mapmover.logging_analytics import log_data_quality_issue_to_cloud

            # Deduplicate mismatches - only log each unique name once
            seen_names = set()
            unique_mismatches = []
            for mismatch in self.mismatches:
                name = mismatch.get('original', '')
                if name and name not in seen_names:
                    seen_names.add(name)
                    unique_mismatches.append(mismatch)

            logged_count = 0
            for mismatch in unique_mismatches:
                issue_type = 'name_mismatch_fuzzy' if mismatch.get('matched') else 'name_mismatch_none'

                log_data_quality_issue_to_cloud(
                    issue_type=issue_type,
                    name=mismatch.get('original', 'unknown'),
                    dataset=dataset_filename,
                    metadata={
                        'source': 'data_ingestion',  # NOT from user requests
                        'matched_to': mismatch.get('matched'),
                        'score': mismatch.get('score'),
                        'type': mismatch.get('type'),
                        'note': 'Logged during ETL data ingestion, not user query'
                    }
                )
                logged_count += 1

            print(f"[NameStandardizer] Logged {logged_count} unique mismatches to hosted control plane (source: data_ingestion)")

        except Exception as e:
            print(f"[NameStandardizer] Error logging to hosted control plane: {e}")


# Convenience function for quick use
def standardize_country_names(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Convenience function to standardize country names in a DataFrame.

    Args:
        df: DataFrame with country names
        column: Column name to standardize

    Returns:
        DataFrame with standardized names
    """
    standardizer = NameStandardizer()
    return standardizer.standardize_country_column(df, column)


if __name__ == "__main__":
    # Test the standardizer
    print("Testing NameStandardizer...")

    std = NameStandardizer()

    # Test some common variants
    test_names = [
        "United States of America",
        "USA",
        "UK",
        "Russia",
        "Russian Federation",
        "South Korea",
        "Republic of Korea",
        "Cote d'Ivoire",
        "Congo, Democratic Republic of the",
        "Czechia",
        "Czech Republic",
        "Unknown Country XYZ",
    ]

    print("\nTesting country name standardization:")
    for name in test_names:
        std_name, exact = std.standardize_country_name(name)
        status = "exact" if exact else "fuzzy/unmatched"
        print(f"  '{name}' -> '{std_name}' ({status})")

    print(f"\nMismatches logged: {len(std.get_mismatches())}")
    for m in std.get_mismatches():
        print(f"  {m}")

    # Test loc_id lookups
    print("\n" + "=" * 50)
    print("Testing loc_id lookup methods:")

    # Name to loc_id
    print("\nget_loc_id_from_name:")
    print(f"  'United States' -> {std.get_loc_id_from_name('United States')}")
    print(f"  'California' (USA) -> {std.get_loc_id_from_name('California', 'USA')}")
    print(f"  'Los Angeles' (USA, level=2) -> {std.get_loc_id_from_name('Los Angeles', 'USA', admin_level=2)}")

    # FIPS to loc_id
    print("\nget_loc_id_from_fips:")
    print(f"  state='06' -> {std.get_loc_id_from_fips('06')}")
    print(f"  state='06', county='037' -> {std.get_loc_id_from_fips('06', '037')}")
    print(f"  state='06', county='06037' -> {std.get_loc_id_from_fips('06', '06037')}")
    print(f"  state='39', county='39055' -> {std.get_loc_id_from_fips('39', '39055')}")

    # ISO to loc_id
    print("\nget_loc_id_from_iso:")
    print(f"  'USA' -> {std.get_loc_id_from_iso('USA')}")
    print(f"  'US' -> {std.get_loc_id_from_iso('US')}")
    print(f"  'US-CA' -> {std.get_loc_id_from_iso('US-CA')}")
    print(f"  'FR-IDF' -> {std.get_loc_id_from_iso('FR-IDF')}")
