# Taginfo Usage Examples

This document provides examples of how to use the Taginfo-enhanced capabilities of the OpenStreetMap MCP server.

## Overview

[Taginfo](https://taginfo.openstreetmap.org) is an OpenStreetMap project that collects information about OSM tags and makes it searchable. The Taginfo capabilities in this MCP server allow you to:

- Perform smart highway searches with intelligent tag selection
- Search for Points of Interest (POIs) with category-based filtering
- Get tag suggestions for autocomplete functionality
- Retrieve usage statistics for any OSM tag key
- Validate if tag combinations are commonly used in the OSM community

## Key Features

### Tag Intelligence
- **Smart Queries**: Automatically selects appropriate tags based on user intent
- **Validation**: Checks if tag combinations are commonly used
- **Suggestions**: Provides autocomplete and alternative tag recommendations
- **Statistics**: Shows real usage data from the global OSM database

### Search Categories
- **Highways**: Major roads, motorways, primary roads, or specific highway types
- **POIs**: Restaurants, shops, tourism, amenities with subcategory support
- **Tags**: Any OSM key-value combinations with usage statistics

## Available Tools

### 1. search_highways_smart

Intelligent highway search that automatically selects appropriate highway types based on your intent.

**Search for major highways in Jakarta:**
```json
{
  "tool": "search_highways_smart",
  "arguments": {
    "intent": "major",
    "bbox": {
      "south": -6.2500,
      "west": 106.8000,
      "north": -6.1500,
      "east": 106.9000
    },
    "limit": 50
  }
}
```

**Search for motorways near Kuala Lumpur:**
```json
{
  "tool": "search_highways_smart",
  "arguments": {
    "intent": "motorway",
    "around": {
      "lat": 3.1390,
      "lon": 101.6869,
      "radius": 5000
    },
    "limit": 25
  }
}
```

**Search for a specific highway type in Singapore:**
```json
{
  "tool": "search_highways_smart",
  "arguments": {
    "intent": "residential",
    "bbox": {
      "south": 1.3000,
      "west": 103.8500,
      "north": 1.3100,
      "east": 103.8600
    },
    "limit": 100
  }
}
```

**Get all highway types in Bengaluru:**
```json
{
  "tool": "search_highways_smart",
  "arguments": {
    "intent": "all",
    "around": {
      "lat": 12.9716,
      "lon": 77.5946,
      "radius": 2000
    },
    "limit": 200
  }
}
```

### 2. search_pois_smart

Smart POI search with category-based filtering and subcategory support.

**Search for restaurants in Bangkok:**
```json
{
  "tool": "search_pois_smart",
  "arguments": {
    "category": "restaurant",
    "bbox": {
      "south": 13.7500,
      "west": 100.5000,
      "north": 13.7600,
      "east": 100.5100
    },
    "limit": 30
  }
}
```

**Search for Italian restaurants in Singapore:**
```json
{
  "tool": "search_pois_smart",
  "arguments": {
    "category": "restaurant",
    "subcategory": "italian",
    "around": {
      "lat": 1.2847,
      "lon": 103.8595,
      "radius": 1500
    },
    "limit": 20
  }
}
```

**Search for supermarkets in Jakarta:**
```json
{
  "tool": "search_pois_smart",
  "arguments": {
    "category": "shop",
    "subcategory": "supermarket",
    "bbox": {
      "south": -6.2200,
      "west": 106.8100,
      "north": -6.2100,
      "east": 106.8200
    },
    "limit": 15
  }
}
```

**Search for museums in Kuala Lumpur:**
```json
{
  "tool": "search_pois_smart",
  "arguments": {
    "category": "tourism",
    "subcategory": "museum",
    "around": {
      "lat": 3.1400,
      "lon": 101.6900,
      "radius": 3000
    },
    "limit": 25
  }
}
```

**Search for hospitals in Bengaluru:**
```json
{
  "tool": "search_pois_smart",
  "arguments": {
    "category": "amenity",
    "subcategory": "hospital",
    "bbox": {
      "south": 12.9600,
      "west": 77.5800,
      "north": 12.9800,
      "east": 77.6000
    },
    "limit": 10
  }
}
```

### 3. get_tag_suggestions

Get autocomplete suggestions for OSM tags based on partial input.

**Get suggestions for highway types:**
```json
{
  "tool": "get_tag_suggestions",
  "arguments": {
    "input": "highway",
    "limit": 15
  }
}
```

**Get suggestions for amenity values:**
```json
{
  "tool": "get_tag_suggestions",
  "arguments": {
    "input": "amenity=rest",
    "limit": 10
  }
}
```

**Get shop type suggestions:**
```json
{
  "tool": "get_tag_suggestions",
  "arguments": {
    "input": "shop=super",
    "limit": 8
  }
}
```

**Get building type suggestions:**
```json
{
  "tool": "get_tag_suggestions",
  "arguments": {
    "input": "building",
    "limit": 20
  }
}
```

**Get cuisine type suggestions:**
```json
{
  "tool": "get_tag_suggestions",
  "arguments": {
    "input": "cuisine=",
    "limit": 25
  }
}
```

### 4. get_tag_stats

Get comprehensive usage statistics for any OSM tag key.

**Get highway tag statistics with popular values:**
```json
{
  "tool": "get_tag_stats",
  "arguments": {
    "key": "highway",
    "include_values": true,
    "values_limit": 20
  }
}
```

**Get amenity usage statistics:**
```json
{
  "tool": "get_tag_stats",
  "arguments": {
    "key": "amenity",
    "include_values": true,
    "values_limit": 30
  }
}
```

**Get basic statistics without values:**
```json
{
  "tool": "get_tag_stats",
  "arguments": {
    "key": "building",
    "include_values": false
  }
}
```

**Get shop tag statistics:**
```json
{
  "tool": "get_tag_stats",
  "arguments": {
    "key": "shop",
    "include_values": true,
    "values_limit": 15
  }
}
```

**Get tourism tag statistics:**
```json
{
  "tool": "get_tag_stats",
  "arguments": {
    "key": "tourism",
    "include_values": true,
    "values_limit": 25
  }
}
```

### 5. validate_osm_tag

Validate if a specific tag combination is commonly used in OSM.

**Validate a common highway type:**
```json
{
  "tool": "validate_osm_tag",
  "arguments": {
    "key": "highway",
    "value": "residential"
  }
}
```

**Validate an amenity type:**
```json
{
  "tool": "validate_osm_tag",
  "arguments": {
    "key": "amenity",
    "value": "restaurant"
  }
}
```

**Validate a shop type:**
```json
{
  "tool": "validate_osm_tag",
  "arguments": {
    "key": "shop",
    "value": "bakery"
  }
}
```

**Check a potentially misspelled tag:**
```json
{
  "tool": "validate_osm_tag",
  "arguments": {
    "key": "amenity",
    "value": "resturant"
  }
}
```

**Validate a cuisine type:**
```json
{
  "tool": "validate_osm_tag",
  "arguments": {
    "key": "cuisine",
    "value": "italian"
  }
}
```

## Response Format

All Taginfo tools return responses in the following format:

```json
{
  "content": [
    {
      "type": "text",
      "text": "JSON-formatted response with Taginfo data"
    }
  ]
}
```

## Smart Query Features

### Highway Search Intents

The `search_highways_smart` tool supports several intent types:

- **"major"** or **"main"**: Primary roads, trunks, motorways
- **"motorway"** or **"freeway"**: Motorways and their links
- **"primary"**: Primary roads specifically
- **"all"** or **"any"**: All highway types
- **Custom types**: Any specific highway type (e.g., "residential", "tertiary")

### POI Categories

The `search_pois_smart` tool supports these main categories:

- **"restaurant"**: Food establishments with optional cuisine subcategory
- **"shop"**: Retail establishments with specific shop type subcategory
- **"tourism"**: Tourist attractions and accommodations
- **"amenity"**: Public facilities and services
- **Custom types**: Any specific amenity, shop, or tourism type

### Tag Suggestion Types

The `get_tag_suggestions` tool supports:

- **Key suggestions**: Partial key input (e.g., "high" → "highway")
- **Value suggestions**: Key-value input (e.g., "amenity=rest" → restaurant, restroom)
- **Fuzzy matching**: Finds similar tags even with typos

## Common Use Cases

### 1. Route Planning

Find major highways for navigation in Jakarta:
```json
{
  "tool": "search_highways_smart",
  "arguments": {
    "intent": "major",
    "bbox": {
      "south": -6.2500,
      "west": 106.8000,
      "north": -6.1500,
      "east": 106.9000
    },
    "limit": 50
  }
}
```

### 2. POI Discovery

Find restaurants in a tourist area in Singapore:
```json
{
  "tool": "search_pois_smart",
  "arguments": {
    "category": "restaurant",
    "around": {
      "lat": 1.2847,
      "lon": 103.8595,
      "radius": 2000
    },
    "limit": 30
  }
}
```

### 3. Tag Validation

Validate tags before adding to OSM:
```json
{
  "tool": "validate_osm_tag",
  "arguments": {
    "key": "shop",
    "value": "bicycle"
  }
}
```

### 4. Data Analysis

Get usage statistics for mapping insights:
```json
{
  "tool": "get_tag_stats",
  "arguments": {
    "key": "highway",
    "include_values": true,
    "values_limit": 50
  }
}
```

### 5. Autocomplete Implementation

Provide tag suggestions in mapping applications:
```json
{
  "tool": "get_tag_suggestions",
  "arguments": {
    "input": "amen",
    "limit": 10
  }
}
```

## Response Data Structures

### Highway Search Response

```json
{
  "results": {
    "elements": [
      {
        "type": "way",
        "id": 123456,
        "tags": {
          "highway": "primary",
          "name": "Main Street"
        }
      }
    ]
  },
  "query_info": {
    "explanation": "Major highways including: motorway, trunk, primary",
    "highway_types": ["motorway", "trunk", "primary"],
    "source": "Taginfo-enhanced query",
    "intent": "major"
  },
  "count": 25
}
```

### POI Search Response

```json
{
  "results": {
    "elements": [
      {
        "type": "node",
        "id": 789012,
        "lat": 1.2847,
        "lon": 103.8595,
        "tags": {
          "amenity": "restaurant",
          "cuisine": "french",
          "name": "Le Bistro"
        }
      }
    ]
  },
  "query_info": {
    "explanation": "restaurant with italian cuisine",
    "tags": {
      "amenity": ["restaurant"],
      "cuisine": ["italian"]
    },
    "source": "Taginfo-enhanced query",
    "category": "restaurant",
    "subcategory": "italian"
  },
  "count": 15
}
```

### Tag Suggestions Response

```json
{
  "suggestions": [
    {
      "key": "highway",
      "value": "residential",
      "count": 45123456,
      "description": "Roads in residential areas",
      "in_wiki": true
    }
  ],
  "input": "highway=res",
  "count": 8
}
```

### Tag Statistics Response

```json
{
  "key": "amenity",
  "stats": {
    "key": "amenity",
    "count_all": 12345678,
    "count_nodes": 8765432,
    "count_ways": 2345678,
    "count_relations": 123456,
    "values": 245,
    "description": "An amenity is a facility used by visitors and residents"
  },
  "popular_values": [
    {
      "value": "restaurant",
      "count_all": 1234567,
      "fraction": 0.0456,
      "description": "A place selling food"
    }
  ],
  "values_count": 20,
  "source": "Taginfo API"
}
```

### Tag Validation Response

```json
{
  "tag": "amenity=resturant",
  "validation": {
    "valid": false,
    "suggestion": "restaurant",
    "count": 1234567
  },
  "source": "Taginfo API"
}
```

## Advanced Features

### 1. Geographic Filtering

Both smart search tools support two types of geographic filtering:

**Bounding Box:**
```json
{
  "bbox": {
    "south": 1.2800,
    "west": 103.8400,
    "north": 1.3000,
    "east": 103.8600
  }
}
```

**Radius Search:**
```json
{
  "around": {
    "lat": 1.2847,
    "lon": 103.8595,
    "radius": 1500
  }
}
```

### 2. Intent-Based Highway Search

The highway search automatically selects appropriate types based on common usage:

- **Major highways**: Includes motorway, trunk, primary, and their links
- **Motorways**: Focuses on high-speed divided highways
- **All types**: Includes residential, tertiary, footway, cycleway, etc.
- **Custom validation**: Checks if your specific highway type is commonly used

### 3. Category-Based POI Search

The POI search intelligently maps categories to OSM tags:

- **Restaurant category**: Maps to amenity=restaurant, fast_food, cafe, bar, pub
- **Shop category**: Uses the shop=* tag with validation
- **Tourism category**: Maps to tourism=* tags
- **Custom handling**: Validates specific subcategories and suggests alternatives

### 4. Smart Tag Suggestions

The suggestion system provides:

- **Fuzzy matching**: Finds tags even with typos
- **Context awareness**: Suggests values based on the key
- **Usage statistics**: Shows how popular each tag is
- **Wiki integration**: Indicates if the tag is documented

## Best Practices

### 1. Use Appropriate Geographic Bounds

- **Urban areas**: Use smaller bounding boxes or radius searches
- **Rural areas**: Larger areas may be needed to find relevant features
- **Performance**: Limit searches to reasonable geographic areas

### 2. Leverage Smart Categories

- **Start broad**: Use general categories like "restaurant" before specific types
- **Use subcategories**: Refine searches with cuisine, shop type, etc.
- **Validate custom types**: Use the validation tool for uncommon tags

### 3. Implement Tag Autocomplete

- **Real-time suggestions**: Call get_tag_suggestions as users type
- **Show statistics**: Display usage counts to help users choose
- **Validate on submit**: Check final tag combinations before saving

### 4. Understand Usage Statistics

- **High counts**: Indicate well-established, widely-used tags
- **Low counts**: May indicate specialized or deprecated tags
- **No results**: Suggests the tag is very rare or potentially incorrect

## Error Handling

The Taginfo tools include validation and will return appropriate error messages for:

- **Invalid geographic bounds**: Malformed bbox or around parameters
- **Invalid limits**: Negative or excessive limit values
- **API connectivity**: Network issues or Taginfo API downtime
- **Empty inputs**: Missing required parameters
- **Rate limiting**: Temporary API restrictions

## Integration Examples

### Building a Tag Editor

```json
[
  {
    "tool": "get_tag_suggestions",
    "arguments": {
      "input": "amen",
      "limit": 10
    }
  },
  {
    "tool": "validate_osm_tag", 
    "arguments": {
      "key": "amenity",
      "value": "restaurant"
    }
  }
]
```

### Quality Assurance Workflow

```json
[
  {
    "tool": "get_tag_stats",
    "arguments": {
      "key": "highway",
      "include_values": true,
      "values_limit": 30
    }
  },
  {
    "tool": "validate_osm_tag",
    "arguments": {
      "key": "highway", 
      "value": "unknown_type"
    }
  }
]
```

### POI Analysis Pipeline

```json
[
  {
    "tool": "search_pois_smart",
    "arguments": {
      "category": "restaurant",
      "bbox": {
        "south": -8.6700,
        "west": 115.2100,
        "north": -8.6600,
        "east": 115.2200
      },
      "limit": 100
    }
  },
  {
    "tool": "get_tag_stats",
    "arguments": {
      "key": "cuisine",
      "include_values": true,
      "values_limit": 25
    }
  }
]
```

## Notes

- **Data Freshness**: Taginfo data is updated regularly from the global OSM database
- **Language Support**: Tag descriptions may be available in multiple languages
- **Performance**: Smart queries use caching and optimization for better response times
- **Coverage**: Statistics reflect global OSM usage patterns
- **Accuracy**: Validation is based on real-world usage, not just tag documentation
- **Community Standards**: Results reflect actual mapping practices of the OSM community

## Related Resources

- **Taginfo Website**: [taginfo.openstreetmap.org](https://taginfo.openstreetmap.org)
- **OSM Wiki**: [wiki.openstreetmap.org](https://wiki.openstreetmap.org)
- **Tag Guidelines**: [wiki.openstreetmap.org/wiki/Tags](https://wiki.openstreetmap.org/wiki/Tags)
- **Tagging Guidelines**: [wiki.openstreetmap.org/wiki/Good_practice](https://wiki.openstreetmap.org/wiki/Good_practice)
