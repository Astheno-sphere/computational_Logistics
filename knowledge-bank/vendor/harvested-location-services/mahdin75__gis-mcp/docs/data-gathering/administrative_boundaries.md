### Administrative Boundaries (GADM via `pygadm`)

The **Administrative Boundaries** tool in GIS-MCP allows you to download official boundaries (countries, provinces, counties, etc.) from the [GADM dataset](https://gadm.org/).

---

#### Installation

To enable boundary downloads, install GIS-MCP with the **administrative-boundaries** extra:

```bash
pip install gis-mcp[administrative-boundaries]
```

#### Parameters

- **region** – Name or alias of the country (e.g. `"Iran"`, `"USA"`, `"UK"`)

- **level** – Administrative level:  
  - `0` → Country boundary  
  - `1` → First-level divisions (provinces, states)  
  - `2` → Second-level divisions (counties, districts)  

- **path** *(optional)* – Custom output folder  
  *(default: package’s `data/administrative_boundaries` directory)*


#### Example Usage

**Prompt:**
```bash
Using gis-mcp download the administrative boundaries of Iran at level 1.
```