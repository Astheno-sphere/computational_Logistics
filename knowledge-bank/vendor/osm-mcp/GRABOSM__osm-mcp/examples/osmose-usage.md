# OSMOSE Quality Assurance Usage Examples

This document provides examples of how to use the OSMOSE quality assurance capabilities of the OpenStreetMap MCP server.

## Overview

[OSMOSE](https://osmose.openstreetmap.fr) (OpenStreetMap Oversight Search Engine) is a powerful quality assurance tool that detects issues in OpenStreetMap data. The OSMOSE capabilities in this MCP server allow you to:

- Search for quality assurance issues with comprehensive filtering (by severity level, type, location, user, etc.)
- Get detailed information about specific issues
- Get statistics about data quality
- Discover available issue categories

## Severity Levels

OSMOSE issues are classified by severity:
- **Level 1**: Major issues (critical errors)
- **Level 2**: Normal issues (standard problems)
- **Level 3**: Minor issues (style and consistency)

## Available Tools

### 1. osmose_search_issues

Search for OSMOSE issues with comprehensive filtering options.

**Basic search in a bounding box in Jakarta:**
```json
{
  "tool": "osmose_search_issues",
  "arguments": {
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

**Search for major issues only in Singapore:**
```json
{
  "tool": "osmose_search_issues",
  "arguments": {
    "bbox": {
      "south": 1.2800,
      "west": 103.8400,
      "north": 1.3000,
      "east": 103.8600
    },
    "level": 1,
    "limit": 20
  }
}
```

**Search by specific issue types in Thailand:**
```json
{
  "tool": "osmose_search_issues",
  "arguments": {
    "item": [3010, 3020, 3030],
    "country": "Thailand",
    "limit": 100
  }
}
```

**Search for issues by specific user in Malaysia:**
```json
{
  "tool": "osmose_search_issues",
  "arguments": {
    "username": "mapper_my",
    "level": [1, 2],
    "full": true,
    "limit": 25
  }
}
```

### 2. osmose_get_issue_details

Get comprehensive details about a specific issue.

```json
{
  "tool": "osmose_get_issue_details",
  "arguments": {
    "issue_id": "123456789"
  }
}
```

### 3. osmose_get_issues_by_country

Get issues for a specific country.

**Get issues in Indonesia:**
```json
{
  "tool": "osmose_get_issues_by_country",
  "arguments": {
    "country": "Indonesia",
    "level": 1,
    "limit": 100
  }
}
```

**Get issues in Vietnam with item filter:**
```json
{
  "tool": "osmose_get_issues_by_country",
  "arguments": {
    "country": "Vietnam",
    "item": 1210,
    "limit": 50
  }
}
```

### 4. osmose_get_issues_by_user

Get issues last modified by a specific user.

**Get issues for user in Singapore:**
```json
{
  "tool": "osmose_get_issues_by_user",
  "arguments": {
    "username": "experienced_mapper",
    "limit": 50
  }
}
```

**Get major issues for user in Philippines:**
```json
{
  "tool": "osmose_get_issues_by_user",
  "arguments": {
    "username": "new_mapper",
    "level": 1,
    "limit": 10
  }
}
```

### 5. osmose_get_stats

Get quality assurance statistics.

**Get statistics for Indonesia:**
```json
{
  "tool": "osmose_get_stats",
  "arguments": {
    "country": "Indonesia"
  }
}
```

**Get statistics for a specific area in Bengaluru:**
```json
{
  "tool": "osmose_get_stats",
  "arguments": {
    "bbox": {
      "south": 12.9600,
      "west": 77.5800,
      "north": 12.9800,
      "east": 77.6000
    }
  }
}
```

### 6. osmose_get_items

Get available issue categories/items.

```json
{
  "tool": "osmose_get_items",
  "arguments": {}
}
```

## Response Format

All OSMOSE tools return responses in the following format:

```json
{
  "content": [
    {
      "type": "text",
      "text": "JSON-formatted response with OSMOSE data"
    }
  ]
}
```

## Common Use Cases

### 1. Monitor Local Quality

Keep track of issues in your city (Jakarta example):
```json
{
  "tool": "osmose_search_issues",
  "arguments": {
    "bbox": {
      "south": -6.2500,
      "west": 106.8000,
      "north": -6.1500,
      "east": 106.9000
    },
    "level": [1, 2],
    "limit": 100
  }
}
```

### 2. Audit Mapping Work

Review mapping quality for a specific user in Thailand:
```json
{
  "tool": "osmose_get_issues_by_user",
  "arguments": {
    "username": "mapper_th",
    "level": 1,
    "limit": 50
  }
}
```

### 3. Country-Wide Analysis

Identify common problem types in a country (Philippines example):
```json
{
  "tool": "osmose_get_stats",
  "arguments": {
    "country": "Philippines"
  }
}
```

### 4. Targeted Cleanup

Find all instances of a specific issue type in a region:
```json
{
  "tool": "osmose_search_issues",
  "arguments": {
    "country": "Vietnam",
    "item": 1210,
    "limit": 200
  }
}
```

## Best Practices

### 1. Filter by Severity
- Start with **Level 1** issues to fix the most critical errors first
- Move to **Level 2** for standard mapping improvements
- Use **Level 3** for fine-tuning and consistency

### 2. Use Geographic Context
- Narrow searches to specific **bounding boxes** for localized cleanup
- Use **country filters** for broader analysis and statistics

### 3. Review Issue Details
- Always check the detailed explanation before making changes
- Use the provided coordinates to locate issues precisely in your editor

### 4. Monitor Stats
- Track data quality trends over time using the stats tool
- Compare different regions to identify where more mapping effort is needed

## Error Handling

The OSMOSE tools will return appropriate error messages for:
- **Invalid parameters**: Malformed bbox, username, or level
- **API connectivity**: Issues reaching the OSMOSE servers
- **Resource limits**: Requests that would return too much data
- **Rate limiting**: Temporary restrictions from the API provider

## Related Resources
- **OSMOSE Wiki**: [wiki.openstreetmap.org/wiki/Osmose](https://wiki.openstreetmap.org/wiki/Osmose)
- **OSMOSE Website**: [osmose.openstreetmap.fr](https://osmose.openstreetmap.fr)
- **Quality Assurance Tools**: [wiki.openstreetmap.org/wiki/Quality_assurance](https://wiki.openstreetmap.org/wiki/Quality_assurance)
