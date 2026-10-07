# Changeset Usage Examples

This document provides examples of how to use the changeset-related capabilities of the OpenStreetMap MCP server.

## Overview

The changeset capabilities allow you to:
- Get detailed information about specific changesets
- Search for changesets using various filters (by user, location, time, etc.)
- Get changeset differences/changes

## Available Tools

### 1. get_changeset

Get detailed information about a specific changeset.

```json
{
  "tool": "get_changeset",
  "arguments": {
    "changeset_id": 123456789,
    "include_discussion": true
  }
}
```

### 2. search_changesets

Search for changesets with various filters.

**Search changesets by user in Singapore:**
```json
{
  "tool": "search_changesets",
  "arguments": {
    "user": "mapper_sg",
    "limit": 20
  }
}
```

**Search changesets in a bounding box in Bengaluru:**
```json
{
  "tool": "search_changesets",
  "arguments": {
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

**Search changesets by time range in Jakarta:**
```json
{
  "tool": "search_changesets",
  "arguments": {
    "bbox": {
      "south": -6.2500,
      "west": 106.8000,
      "north": -6.1500,
      "east": 106.9000
    },
    "time": "2024-01-01T00:00:00Z,2024-12-31T23:59:59Z",
    "limit": 50
  }
}
```

### 3. get_changeset_diff

Get the diff/changes for a specific changeset.

```json
{
  "tool": "get_changeset_diff",
  "arguments": {
    "changeset_id": 123456789
  }
}
```

## Response Format

All changeset tools return responses in the following format:

```json
{
  "content": [
    {
      "type": "text",
      "text": "JSON-formatted response with changeset data"
    }
  ]
}
```

## Changeset Data Structure

The `get_changeset` tool returns data including:
- `id`: Unique changeset identifier
- `created_at`: Creation timestamp
- `closed_at`: Closure timestamp
- `user`: Username of the mapper
- `uid`: User ID
- `min_lat`, `min_lon`, `max_lat`, `max_lon`: Bounding box of changes
- `num_changes`: Number of edits in the changeset
- `comments_count`: Number of comments
- `tags`: Metadata tags (e.g., `comment`, `source`, `created_by`)
- `discussion`: Array of comments (if `include_discussion` is true)

The `search_changesets` tool returns an array of changeset summaries.

The `get_changeset_diff` tool returns the OSM XML diff format (osmChange) representing the additions, modifications, and deletions.

## Common Use Cases

### 1. Monitor Local Edits

Keep track of recent changes in a specific area (Singapore example):
```json
{
  "tool": "search_changesets",
  "arguments": {
    "bbox": {
      "south": 1.2800,
      "west": 103.8400,
      "north": 1.3000,
      "east": 103.8600
    },
    "limit": 50
  }
}
```

### 2. Audit User Contributions

Review changes made by a specific mapper in Bengaluru:
```json
{
  "tool": "search_changesets",
  "arguments": {
    "user": "experienced_mapper",
    "limit": 100
  }
}
```

### 3. Analyze Historical Changes

Search for edits made during a specific event or mapping campaign in Jakarta:
```json
{
  "tool": "search_changesets",
  "arguments": {
    "time": "2024-05-01T00:00:00Z,2024-05-31T23:59:59Z",
    "limit": 200
  }
}
```

## Best Practices

### 1. Use Appropriate Filters
- Combine `user` and `time` filters for targeted auditing
- Use `bbox` to narrow results to a specific geographic region
- Set a reasonable `limit` to avoid excessive data transfer

### 2. Review Discussion
- Check the `discussion` field to understand context and feedback on changesets
- Look for comments explaining the source and purpose of edits

### 3. Examine Diffs
- Use `get_changeset_diff` for detailed technical review of exactly what changed
- Be aware that diffs can be large for changesets with many edits

### 4. Understand num_changes
- Large values for `num_changes` (thousands of edits) often indicate automated imports or large-scale cleanup
- Smaller values are typical for manual mapping

## Error Handling

The changeset tools will return appropriate error messages for:
- **Invalid changeset IDs**: Non-existent or malformed IDs
- **Invalid geographic bounds**: Malformed bbox parameters
- **API connectivity**: Issues reaching the main OpenStreetMap servers
- **Resource limits**: Requests that would return too much data
- **Rate limiting**: Temporary restrictions from the OSM API provider

## Related Resources
- **OSM Wiki (Changeset)**: [wiki.openstreetmap.org/wiki/Changeset](https://wiki.openstreetmap.org/wiki/Changeset)
- **OSM Wiki (Diff)**: [wiki.openstreetmap.org/wiki/OsmChange](https://wiki.openstreetmap.org/wiki/OsmChange)
- **Changeset Discussion**: [wiki.openstreetmap.org/wiki/Changeset_Discussion](https://wiki.openstreetmap.org/wiki/Changeset_Discussion)
