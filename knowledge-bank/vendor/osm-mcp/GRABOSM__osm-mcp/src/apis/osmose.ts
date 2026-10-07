import type { 
  OSMOSEIssue, 
  OSMOSEIssueDetails, 
  OSMOSESearchParams, 
  OSMOSESearchResponse, 
  OSMOSEItem, 
  OSMOSEStats
} from '../types.js';

export class OSMOSEClient {
  private baseUrl = 'https://osmose.openstreetmap.fr/api/0.3';
  
  /**
   * Search for OSMOSE issues with various filters
   */
  async searchIssues(params: OSMOSESearchParams): Promise<OSMOSESearchResponse> {
    const queryParams = new URLSearchParams();
    
    if (params.bbox) {
      queryParams.append('bbox', `${params.bbox.west},${params.bbox.south},${params.bbox.east},${params.bbox.north}`);
    }
    
    if (params.item) {
      if (Array.isArray(params.item)) {
        params.item.forEach(item => queryParams.append('item', item.toString()));
      } else {
        queryParams.append('item', params.item.toString());
      }
    }
    
    if (params.level) {
      if (Array.isArray(params.level)) {
        params.level.forEach(level => queryParams.append('level', level.toString()));
      } else {
        queryParams.append('level', params.level.toString());
      }
    }
    
    if (params.country) {
      queryParams.append('country', params.country);
    }
    
    if (params.username) {
      queryParams.append('username', params.username);
    }
    
    if (params.limit) {
      queryParams.append('limit', params.limit.toString());
    }
    
    if (params.full) {
      queryParams.append('full', 'true');
    }
    
    const url = `${this.baseUrl}/issues?${queryParams.toString()}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      const issues: OSMOSEIssue[] = data.issues || [];
      
      return {
        issues: issues.map(issue => this.parseIssue(issue)),
        count: issues.length,
        bbox: params.bbox,
        search_params: params
      };
    } catch (error) {
      throw new Error(`Failed to search OSMOSE issues: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get detailed information about a specific issue
   */
  async getIssueDetails(issueId: string): Promise<OSMOSEIssueDetails> {
    const url = `${this.baseUrl}/issue/${issueId}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      return this.parseIssueDetails(data);
    } catch (error) {
      throw new Error(`Failed to get OSMOSE issue details: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get issues by item/category
   */
  async getIssuesByItem(item: number | number[], options: Partial<OSMOSESearchParams> = {}): Promise<OSMOSESearchResponse> {
    return this.searchIssues({ ...options, item });
  }

  /**
   * Get issues by country
   */
  async getIssuesByCountry(country: string, options: Partial<OSMOSESearchParams> = {}): Promise<OSMOSESearchResponse> {
    return this.searchIssues({ ...options, country });
  }

  /**
   * Get issues by username
   */
  async getIssuesByUsername(username: string, options: Partial<OSMOSESearchParams> = {}): Promise<OSMOSESearchResponse> {
    return this.searchIssues({ ...options, username });
  }

  /**
   * Get OSMOSE statistics (calculated from search results with priority-based fetching)
   */
  async getStats(params: Partial<OSMOSESearchParams> = {}): Promise<OSMOSEStats> {
    try {
      // Fetch issues by priority level to ensure we get major issues first
      // OSMOSE API max limit is 500, so we'll fetch by level to get comprehensive stats
      
      const allIssues: OSMOSEIssue[] = [];
      const maxPerLevel = 500; // OSMOSE API maximum limit
      const fetchResults: Record<number, number> = {};
      
      // Priority order: 1=Major, 2=Normal, 3=Minor
      const levels = [1, 2, 3] as const;
      
      for (const level of levels) {
        try {
          console.log(`Fetching level ${level} issues for ${params.country || 'bounding box'}`);
          const levelResults = await this.searchIssues({ 
            ...params, 
            level: level,
            limit: maxPerLevel 
          });
          
          fetchResults[level] = levelResults.issues.length;
          console.log(`Fetched ${levelResults.issues.length} level ${level} issues`);
          
          allIssues.push(...levelResults.issues);
          
          // If we got fewer than maxPerLevel, we've exhausted this level
          if (levelResults.issues.length < maxPerLevel) {
            // Continue to next level
          }
        } catch (levelError) {
          // Log error but continue with other levels
          console.error(`Failed to fetch level ${level} issues:`, levelError);
          fetchResults[level] = 0;
        }
      }
      
      console.log(`Total issues fetched: ${allIssues.length}`, fetchResults);
      
      // Calculate statistics from all collected issues
      const stats: OSMOSEStats = {
        total: allIssues.length,
        by_level: {},
        by_item: {},
        by_country: undefined
      };
      
      // Count issues by level
      for (const issue of allIssues) {
        const level = issue.level;
        stats.by_level[level] = (stats.by_level[level] || 0) + 1;
      }
      
      // Count issues by item
      for (const issue of allIssues) {
        const item = issue.item;
        stats.by_item[item] = (stats.by_item[item] || 0) + 1;
      }
      
      console.log('Calculated stats:', stats);
      
      // Add metadata about the prioritized fetching
      (stats as any).fetch_metadata = {
        total_fetched: allIssues.length,
        levels_fetched: levels.length,
        max_per_level: maxPerLevel,
        prioritized_by_severity: true,
        fetch_details: fetchResults,
        note: "Major issues (level 1) fetched first, followed by Normal (level 2), then Minor (level 3)"
      };
      
      return stats;
    } catch (error) {
      console.error('Error in getStats:', error);
      throw new Error(`Failed to get OSMOSE statistics: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get available issue items/categories
   */
  async getItems(): Promise<OSMOSEItem[]> {
    const url = `${this.baseUrl}/items`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      return data.items ? data.items.map((item: any) => this.parseItem(item)) : [];
    } catch (error) {
      throw new Error(`Failed to get OSMOSE items: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get list of available countries/regions
   */
  async getCountries(): Promise<string[]> {
    const url = `${this.baseUrl}/countries`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      return data.countries || [];
    } catch (error) {
      throw new Error(`Failed to get OSMOSE countries: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Parse issue data from API response
   */
  private parseIssue(issueData: any): OSMOSEIssue {
    return {
      id: issueData.id?.toString() || '',
      lat: parseFloat(issueData.lat || '0'),
      lon: parseFloat(issueData.lon || '0'),
      item: parseInt(issueData.item || '0'),
      class: parseInt(issueData.class || '0'),
      subclass: issueData.subclass ? parseInt(issueData.subclass) : undefined,
      title: issueData.title || '',
      subtitle: issueData.subtitle || undefined,
      level: parseInt(issueData.level || '3'),
      update: issueData.update || '',
      username: issueData.username || undefined,
      elems: issueData.elems || undefined,
      tags: issueData.tags || undefined,
      fixes: issueData.fixes || undefined
    };
  }

  /**
   * Parse detailed issue data from API response
   */
  private parseIssueDetails(issueData: any): OSMOSEIssueDetails {
    return {
      id: issueData.id?.toString() || '',
      lat: parseFloat(issueData.lat || '0'),
      lon: parseFloat(issueData.lon || '0'),
      item: parseInt(issueData.item || '0'),
      class: parseInt(issueData.class || '0'),
      subclass: issueData.subclass ? parseInt(issueData.subclass) : undefined,
      title: issueData.title || '',
      subtitle: issueData.subtitle || undefined,
      level: parseInt(issueData.level || '3'),
      update: issueData.update || '',
      username: issueData.username || undefined,
      elems: issueData.elems || undefined,
      tags: issueData.tags || undefined,
      fixes: issueData.fixes || undefined,
      detail: issueData.detail || undefined,
      fix_description: issueData.fix || undefined,
      trap: issueData.trap || undefined,
      example: issueData.example || undefined
    };
  }

  /**
   * Parse item data from API response
   */
  private parseItem(itemData: any): OSMOSEItem {
    return {
      item: parseInt(itemData.item || '0'),
      title: itemData.title || '',
      level: parseInt(itemData.level || '3'),
      tags: Array.isArray(itemData.tags) ? itemData.tags : [],
      detail: itemData.detail || undefined,
      fix: itemData.fix || undefined,
      trap: itemData.trap || undefined,
      example: itemData.example || undefined
    };
  }

  /**
   * Parse statistics data from API response
   */
  private parseStats(statsData: any): OSMOSEStats {
    return {
      total: parseInt(statsData.total || '0'),
      by_level: statsData.by_level || {},
      by_item: statsData.by_item || {},
      by_country: statsData.by_country || undefined
    };
  }
}