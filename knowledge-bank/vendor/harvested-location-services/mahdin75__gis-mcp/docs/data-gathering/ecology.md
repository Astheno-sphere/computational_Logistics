### Ecology Data (Currently GBIF via `pygbif`)

Currently, the **Ecology Data** tool in GIS-MCP allows you to download species occurrence records and taxonomic information from the [Global Biodiversity Information Facility (GBIF)](https://www.gbif.org/).

---

#### Installation

To enable ecology data downloads, install GIS-MCP with the **ecology** extra:

```bash
pip install gis-mcp[ecology]
```

---

#### Available Operations

- `get_species_info` – Retrieve taxonomic information for a given species name.
- `download_species_occurrences` – Download occurrence records for a given species and save as JSON.

---

#### Example Usage

**Prompt:**

```bash
Using gis-mcp download occurrence records for Panthera leo (African lion) and save as JSON.
```

**Prompt:**

```bash
Using gis-mcp get taxonomic information for Quercus robur (English oak).
```
