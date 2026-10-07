import { parseStringPromise } from 'xml2js';
import type { 
  OSMChangeset, 
  ChangesetSearchParams, 
  ChangesetDiff, 
  ChangesetElement, 
  ChangesetResponse
} from '../types.js';

export class ChangesetClient {
  private baseUrl = 'https://api.openstreetmap.org/api/0.6';
  
  /**
   * Get changeset details by ID
   */
  async getChangeset(changesetId: number, includeDiscussion: boolean = false): Promise<OSMChangeset> {
    const url = `${this.baseUrl}/changeset/${changesetId}${includeDiscussion ? '?include_discussion=true' : ''}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const xmlData = await response.text();
      const parsedData = await parseStringPromise(xmlData);
      
      return this.parseChangeset(parsedData.osm.changeset[0]);
    } catch (error) {
      throw new Error(`Failed to fetch changeset ${changesetId}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Search for changesets with various filters
   */
  async searchChangesets(params: ChangesetSearchParams): Promise<ChangesetResponse> {
    const queryParams = new URLSearchParams();
    
    // Handle user parameter: if string, treat as username (map to display_name), if number, use as user ID
    if (params.user !== undefined) {
      if (typeof params.user === 'string') {
        // Username (string) - map to display_name for OSM API
        queryParams.append('display_name', params.user);
      } else if (typeof params.user === 'number') {
        // User ID (number) - use as user parameter
        queryParams.append('user', params.user.toString());
      }
    }
    // Backward compatibility: if display_name is provided and user is not, use display_name
    if (params.display_name && params.user === undefined) {
      queryParams.append('display_name', params.display_name);
    }
    if (params.bbox) {
      queryParams.append('bbox', `${params.bbox.west},${params.bbox.south},${params.bbox.east},${params.bbox.north}`);
    }
    if (params.time) queryParams.append('time', params.time);
    if (params.open !== undefined) queryParams.append('open', params.open.toString());
    if (params.closed !== undefined) queryParams.append('closed', params.closed.toString());
    if (params.changesets && params.changesets.length > 0) {
      queryParams.append('changesets', params.changesets.join(','));
    }
    if (params.limit) queryParams.append('limit', params.limit.toString());
    
    const url = `${this.baseUrl}/changesets?${queryParams.toString()}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const xmlData = await response.text();
      const parsedData = await parseStringPromise(xmlData);
      
      const changesets = parsedData.osm.changeset || [];
      return {
        changesets: changesets.map((cs: any) => this.parseChangeset(cs))
      };
    } catch (error) {
      throw new Error(`Failed to search changesets: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get changeset diff/changes
   */
  async getChangesetDiff(changesetId: number): Promise<ChangesetDiff> {
    const url = `${this.baseUrl}/changeset/${changesetId}/download`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const xmlData = await response.text();
      const parsedData = await parseStringPromise(xmlData);
      
      return this.parseChangesetDiff(changesetId, parsedData);
    } catch (error) {
      throw new Error(`Failed to fetch changeset diff ${changesetId}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Parse changeset XML data
   */
  private parseChangeset(changesetXml: any): OSMChangeset {
    const changeset: OSMChangeset = {
      id: parseInt(changesetXml.$.id),
      user: changesetXml.$.user,
      uid: changesetXml.$.uid ? parseInt(changesetXml.$.uid) : undefined,
      created_at: changesetXml.$.created_at,
      closed_at: changesetXml.$.closed_at || null,
      open: changesetXml.$.open === 'true',
      min_lat: changesetXml.$.min_lat ? parseFloat(changesetXml.$.min_lat) : undefined,
      max_lat: changesetXml.$.max_lat ? parseFloat(changesetXml.$.max_lat) : undefined,
      min_lon: changesetXml.$.min_lon ? parseFloat(changesetXml.$.min_lon) : undefined,
      max_lon: changesetXml.$.max_lon ? parseFloat(changesetXml.$.max_lon) : undefined,
      num_changes: changesetXml.$.num_changes ? parseInt(changesetXml.$.num_changes) : undefined,
      comments_count: changesetXml.$.comments_count ? parseInt(changesetXml.$.comments_count) : undefined
    };

    // Parse tags
    if (changesetXml.tag) {
      changeset.tags = {};
      for (const tag of changesetXml.tag) {
        changeset.tags[tag.$.k] = tag.$.v;
      }
    }

    // Parse discussion
    if (changesetXml.discussion && changesetXml.discussion[0] && changesetXml.discussion[0].comment) {
      changeset.discussion = changesetXml.discussion[0].comment.map((comment: any) => ({
        id: parseInt(comment.$.id),
        date: comment.$.date,
        user: comment.$.user,
        uid: comment.$.uid ? parseInt(comment.$.uid) : undefined,
        text: comment.text ? comment.text[0] : ''
      }));
    }

    return changeset;
  }

  /**
   * Parse changeset diff XML data
   */
  private parseChangesetDiff(changesetId: number, diffXml: any): ChangesetDiff {
    const elements: ChangesetElement[] = [];
    
    // Parse create actions
    if (diffXml.osmChange && diffXml.osmChange.create) {
      for (const create of diffXml.osmChange.create) {
        this.parseChangesetElements(create, 'create', elements);
      }
    }

    // Parse modify actions  
    if (diffXml.osmChange && diffXml.osmChange.modify) {
      for (const modify of diffXml.osmChange.modify) {
        this.parseChangesetElements(modify, 'modify', elements);
      }
    }

    // Parse delete actions
    if (diffXml.osmChange && diffXml.osmChange.delete) {
      for (const deleteAction of diffXml.osmChange.delete) {
        this.parseChangesetElements(deleteAction, 'delete', elements);
      }
    }

    return {
      changeset_id: changesetId,
      elements
    };
  }

  /**
   * Parse changeset elements from XML
   */
  private parseChangesetElements(xmlData: any, action: 'create' | 'modify' | 'delete', elements: ChangesetElement[]) {
    ['node', 'way', 'relation'].forEach(elementType => {
      if (xmlData[elementType]) {
        for (const element of xmlData[elementType]) {
          const changesetElement: ChangesetElement = {
            type: elementType as 'node' | 'way' | 'relation',
            id: parseInt(element.$.id),
            version: element.$.version ? parseInt(element.$.version) : undefined,
            action
          };

          // Add coordinates for nodes
          if (elementType === 'node' && element.$.lat && element.$.lon) {
            (changesetElement as any).lat = parseFloat(element.$.lat);
            (changesetElement as any).lon = parseFloat(element.$.lon);
          }

          // Add changeset ID
          if (element.$.changeset) {
            (changesetElement as any).changeset = parseInt(element.$.changeset);
          }

          // Add timestamp
          if (element.$.timestamp) {
            (changesetElement as any).timestamp = element.$.timestamp;
          }

          // Add user info
          if (element.$.user) {
            (changesetElement as any).user = element.$.user;
          }
          if (element.$.uid) {
            (changesetElement as any).uid = parseInt(element.$.uid);
          }

          // Parse tags
          if (element.tag) {
            const tags: Record<string, string> = {};
            for (const tag of element.tag) {
              tags[tag.$.k] = tag.$.v;
            }
            (changesetElement as any).tags = tags;
          }

          // Parse node references for ways
          if (elementType === 'way' && element.nd) {
            const nodeRefs: number[] = [];
            for (const nd of element.nd) {
              nodeRefs.push(parseInt(nd.$.ref));
            }
            (changesetElement as any).nd = nodeRefs;
          }

          // Parse members for relations
          if (elementType === 'relation' && element.member) {
            const members: Array<{type: string, ref: number, role: string}> = [];
            for (const member of element.member) {
              members.push({
                type: member.$.type,
                ref: parseInt(member.$.ref),
                role: member.$.role || ''
              });
            }
            (changesetElement as any).member = members;
          }

          elements.push(changesetElement);
        }
      }
    });
  }
} 