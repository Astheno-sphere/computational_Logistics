import { validateLimit } from '../utils/validation.js';

export interface TagValue {
  value: string;
  count_all: number;
  count_all_fraction: number;
  description?: string;
}

export interface TagStats {
  key: string;
  count_all: number;
  count_all_fraction: number;
  users_all: number;
  values: number;
  description?: string;
}

export interface TagDocumentation {
  key: string;
  value?: string;
  title: string;
  description: string;
  lang: string;
  url: string;
  on_node: boolean;
  on_way: boolean;
  on_relation: boolean;
  on_area: boolean;
}

export interface TagSuggestion {
  key: string;
  value?: string;
  count: number;
  description?: string;
  in_wiki: boolean;
}

export class TaginfoClient {
  private readonly baseUrl = 'https://taginfo.openstreetmap.org/api/4';

  /**
   * Get popular values for a specific key
   */
  async getPopularValuesForKey(key: string, limit = 10): Promise<TagValue[]> {
    validateLimit(limit);
    
    const url = `${this.baseUrl}/key/values?key=${encodeURIComponent(key)}&sortname=count_all&sortorder=desc&rp=${limit}&page=1`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Taginfo API error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Handle error responses from Taginfo API
      if (data.error) {
        throw new Error(`Taginfo API error: ${data.error}`);
      }
      
      return data.data || [];
    } catch (error) {
      throw new Error(`Failed to fetch values for key "${key}": ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Get statistics for a specific key
   */
  async getKeyStats(key: string): Promise<TagStats | null> {
    const url = `${this.baseUrl}/key/stats?key=${encodeURIComponent(key)}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Taginfo API error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      const stats = data.data || [];
      
      // The API returns an array of stats, we want the "all" type summary
      const allStats = stats.find((stat: any) => stat.type === 'all');
      
      if (!allStats) {
        return null;
      }
      
      return {
        key: key,
        count_all: allStats.count,
        count_all_fraction: allStats.count_fraction,
        users_all: 0, // Not available in the stats endpoint
        values: allStats.values,
        description: undefined // Not available in the stats endpoint
      };
    } catch (error) {
      throw new Error(`Failed to fetch stats for key "${key}": ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Get documentation for a specific tag
   */
  async getTagDocumentation(key: string, value?: string): Promise<TagDocumentation[]> {
    const url = value 
      ? `${this.baseUrl}/tag/wiki_pages?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}`
      : `${this.baseUrl}/key/wiki_pages?key=${encodeURIComponent(key)}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Taginfo API error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      return data.data || [];
    } catch (error) {
      throw new Error(`Failed to fetch documentation for "${key}${value ? `=${value}` : ''}": ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Search for keys that match a pattern
   */
  async searchKeys(query: string, limit = 10): Promise<TagStats[]> {
    validateLimit(limit);
    
    const url = `${this.baseUrl}/keys/all?query=${encodeURIComponent(query)}&sortname=count_all&sortorder=desc&rp=${limit}&page=1`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Taginfo API error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Handle error responses from Taginfo API
      if (data.error) {
        throw new Error(`Taginfo API error: ${data.error}`);
      }
      
      return data.data || [];
    } catch (error) {
      throw new Error(`Failed to search keys with query "${query}": ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Get suggestions for tags based on partial input
   */
  async getTagSuggestions(input: string, limit = 10): Promise<TagSuggestion[]> {
    validateLimit(limit);
    
    // If input contains '=', split into key and value
    const [key, value] = input.includes('=') ? input.split('=', 2) : [input, ''];
    
    if (value) {
      // Search for values of a specific key
      const values = await this.getPopularValuesForKey(key, limit);
      return values
        .filter(v => v.value.toLowerCase().includes(value.toLowerCase()))
        .map(v => ({
          key,
          value: v.value,
          count: v.count_all,
          description: v.description,
          in_wiki: !!v.description
        }));
    } else {
      // Search for keys
      const keys = await this.searchKeys(key, limit);
      return keys.map(k => ({
        key: k.key,
        count: k.count_all,
        description: k.description,
        in_wiki: !!k.description
      }));
    }
  }

  /**
   * Get major highway types based on usage statistics
   */
  async getMajorHighwayTypes(limit = 10): Promise<string[]> {
    // Fetch more values since major highways aren't in the top 10
    const values = await this.getPopularValuesForKey('highway', 50);
    
    // Filter for major highway types based on common OSM practice
    const majorTypes = ['motorway', 'trunk', 'primary', 'motorway_link', 'trunk_link', 'primary_link'];
    
    return values
      .map(v => v.value)
      .filter(value => majorTypes.includes(value))
      .slice(0, limit);
  }

  /**
   * Get common amenity types
   */
  async getCommonAmenities(limit = 20): Promise<string[]> {
    const values = await this.getPopularValuesForKey('amenity', limit);
    return values.map(v => v.value);
  }

  /**
   * Get common shop types
   */
  async getCommonShops(limit = 20): Promise<string[]> {
    const values = await this.getPopularValuesForKey('shop', limit);
    return values.map(v => v.value);
  }

  /**
   * Get common tourism types
   */
  async getCommonTourism(limit = 20): Promise<string[]> {
    const values = await this.getPopularValuesForKey('tourism', limit);
    return values.map(v => v.value);
  }

  /**
   * Validate if a tag key-value combination is commonly used
   */
  async validateTag(key: string, value: string): Promise<{ valid: boolean; count?: number; suggestion?: string }> {
    try {
      const values = await this.getPopularValuesForKey(key, 100);
      const exactMatch = values.find(v => v.value === value);
      
      if (exactMatch) {
        return { valid: true, count: exactMatch.count_all };
      }
      
      // Find similar values
      const similar = values.find(v => 
        v.value.toLowerCase().includes(value.toLowerCase()) || 
        value.toLowerCase().includes(v.value.toLowerCase())
      );
      
      if (similar) {
        return { 
          valid: false, 
          suggestion: similar.value,
          count: similar.count_all 
        };
      }
      
      return { valid: false };
    } catch (error) {
      return { valid: false };
    }
  }
} 