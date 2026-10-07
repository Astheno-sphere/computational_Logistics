# OpenStreetMap MCP Server

A powerful **Model Context Protocol (MCP)** server for OpenStreetMap, providing **30 tools** for geocoding, routing, quality assurance, and data analysis. Optimized for AI assistants like Cursor and Claude.

**A community project by Grab** — providing open-source mapping tools to help developers and researchers work with OpenStreetMap data more effectively.

---

## 🎯 Quick Start

### 1️⃣ Installation
```bash
git clone https://github.com/GRABOSM/osm-mcp.git
cd osm-mcp
npm install
npm run build
```

### 2️⃣ Configure AI Integration

#### **Cursor AI**
1. Open Cursor **Settings** → **Features** → **Model Context Protocol**.
2. Add a new server with:
   - **Type**: `command`
   - **Command**: `node /absolute/path/to/osm-mcp/dist/index.js`

#### **Cursor Desktop**
Add this to your `mcp.json`:
```json
{
  "mcpServers": {
    "osm-mcp": {
      "command": "node",
      "args": ["/absolute/path/to/osm-mcp/dist/index.js"]
    }
  }
}
```

#### **Claude Desktop**
Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "osm": {
      "command": "node",
      "args": ["/absolute/path/to/osm-mcp/dist/index.js"]
    }
  }
}
```

### 3️⃣ Start Using
Try asking your AI:
- "Find coffee shops in Makati, Manila"
- "Calculate a 15-minute driving isochrone from Grab HQ Singapore"
- "Get directions from Changi Airport to Marina Bay Sands"

---

## 🚀 Key Features

*   **Geocoding**: Search addresses and landmarks globally.
*   **Routing (OSRM)**: Turn-by-turn directions, distance matrices, and route optimization.
*   **Smart POI**: Find restaurants, shops, and attractions with intelligent tag detection.
*   **Quality Assurance (OSMOSE)**: Detect mapping errors and monitor data quality.
*   **Changeset Analysis**: Analyze recent edits and user contributions.
*   **Tag Intelligence (Taginfo)**: Real-world tag usage statistics and validation.
*   **Dual Interface**: Use via MCP (AI tools) or HTTP REST API.

---

## 🛠️ Tool Reference (30 Tools)

### 🗺️ Geocoding (4)
1. `search_location`: Search for places and addresses.
2. `reverse_geocode`: Get address from coordinates.
3. `search_structured`: Search by street, city, country, etc.
4. `get_place_details`: Get full details of an OSM element.

### 📍 Points of Interest (3)
5. `search_pois`: General POI search (amenities, shops, etc.).
6. `search_pois_smart`: Intelligent POI search with category detection.
7. `find_amenities_nearby`: Locate facilities within a specific radius.

### 🛣️ Routing & Navigation (5)
8. `get_osrm_route`: Detailed turn-by-turn directions.
9. `get_distance_matrix`: Travel times and distances between multiple points.
10. `optimize_route`: Find the best route through multiple stops (TSP).
11. `map_match_gps`: Snap GPS traces to the road network.
12. `calculate_isochrone`: Area reachable within a time limit.

### 📊 OSM Data Analysis (6)
13. `search_highways_smart`: Smart search for roads and motorways.
14. `get_elements_in_bounds`: Get all data within a bounding box.
15. `search_by_tags`: Find elements by specific OSM tags.
16. `get_route_data`: Extract road geometry for custom use.
17. `execute_overpass_query`: Run advanced Overpass QL queries.
18. `snap_to_roads`: Find the nearest road for any point.

### 🔄 Changeset Analysis (3)
19. `get_changeset`: Details of a specific mapping edit.
20. `search_changesets`: Find edits by user, time, or location.
21. `get_changeset_diff`: View exact changes made in an edit.

### 🔍 Quality Assurance (6)
22. `osmose_search_issues`: Find data errors with filters.
23. `osmose_get_issue_details`: Details of a specific quality issue.
24. `osmose_get_issues_by_country`: Quality issues by nation.
25. `osmose_get_issues_by_user`: Issues related to a specific user.
26. `osmose_get_stats`: Data quality metrics and charts.
27. `osmose_get_items`: List of detectable issue categories.

### 🏷️ Tag Intelligence (3)
28. `get_tag_suggestions`: Autocomplete for OSM tags.
29. `get_tag_stats`: Usage statistics for any tag.
30. `validate_osm_tag`: Check if a tag combination is proper.

---

## 💡 Example Usage

### Navigation
> "Get directions from KL Sentral to Petronas Twin Towers"

### Urban Planning
> "Calculate 30-minute driving isochrone from Grab HQ Singapore"

### Quality Monitoring
> "Analyze recent mapping activity in Bengaluru"

---

## 🌐 HTTP API Mode
Run as a standalone server:
```bash
npm run dev:http
```
Access docs at: `http://localhost:8888/api/info`

---

## 🛠️ Troubleshooting
- **Absolute Paths**: Always use full paths in AI tool configurations.
- **Build First**: Ensure you run `npm run build` after any changes.
- **Node Version**: Use Node.js v18 or higher.

---

## 📄 License
This project is licensed under the **MIT License**.

---

## 🙏 Credits
- **OpenStreetMap Contributors**
- **OSRM**, **Nominatim**, **Overpass**, **OSMOSE**, **Taginfo** communities.
