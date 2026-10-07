import { TaginfoClient } from '../apis/taginfo.js';
import type { BoundingBox } from '../types.js';

export interface SmartQueryOptions {
  bbox?: BoundingBox;
  around?: {
    lat: number;
    lon: number;
    radius: number;
  };
  limit?: number;
}

export interface HighwayQueryResult {
  query: string;
  explanation: string;
  highwayTypes: string[];
  source: string;
}

export interface POIQueryResult {
  query: string;
  explanation: string;
  tags: Record<string, string[]>;
  source: string;
}

export class SmartQueryBuilder {
  private taginfo: TaginfoClient;

  constructor() {
    this.taginfo = new TaginfoClient();
  }

  /**
   * Build a smart highway query based on user intent
   */
  async buildHighwayQuery(
    intent: 'major' | 'all' | 'motorway' | 'primary' | 'residential' | string,
    options: SmartQueryOptions = {}
  ): Promise<HighwayQueryResult> {
    let highwayTypes: string[] = [];
    let explanation = '';

    switch (intent.toLowerCase()) {
      case 'major':
      case 'main':
      case 'primary':
        highwayTypes = await this.taginfo.getMajorHighwayTypes();
        explanation = `Major highways including: ${highwayTypes.join(', ')}`;
        break;
      
      case 'motorway':
      case 'highway':
      case 'freeway':
        highwayTypes = ['motorway', 'motorway_link'];
        explanation = 'Motorways and their connecting links';
        break;
      
      case 'all':
      case 'any': {
        const allTypes = await this.taginfo.getPopularValuesForKey('highway', 20);
        highwayTypes = allTypes.map(v => v.value);
        explanation = `All highway types (${highwayTypes.length} types)`;
        break;
      }
      
      default: {
        // Try to validate the custom intent as a highway type
        const validation = await this.taginfo.validateTag('highway', intent);
        if (validation.valid) {
          highwayTypes = [intent];
          explanation = `Specific highway type: ${intent}`;
        } else if (validation.suggestion) {
          highwayTypes = [validation.suggestion];
          explanation = `Using suggested highway type: ${validation.suggestion} (did you mean this instead of "${intent}"?)`;
        } else {
          // Fallback to major highways
          highwayTypes = await this.taginfo.getMajorHighwayTypes();
          explanation = `Unknown highway type "${intent}", using major highways instead: ${highwayTypes.join(', ')}`;
        }
      }
    }

    const query = this.buildOverpassQuery('way', { highway: highwayTypes }, options);
    
    return {
      query,
      explanation,
      highwayTypes,
      source: 'Taginfo-enhanced query'
    };
  }

  /**
   * Build a smart POI query based on category
   */
  async buildPOIQuery(
    category: 'restaurant' | 'shop' | 'tourism' | 'amenity' | string,
    subcategory?: string,
    options: SmartQueryOptions = {}
  ): Promise<POIQueryResult> {
    const tags: Record<string, string[]> = {};
    let explanation = '';

    switch (category.toLowerCase()) {
      case 'restaurant':
      case 'food':
      case 'dining':
        tags.amenity = ['restaurant', 'fast_food', 'cafe', 'bar', 'pub'];
        if (subcategory) {
          // Validate cuisine type
          const validation = await this.taginfo.validateTag('cuisine', subcategory);
          if (validation.valid) {
            tags.cuisine = [subcategory];
            explanation = `${category} with ${subcategory} cuisine`;
          } else {
            explanation = `${category} (cuisine "${subcategory}" not commonly used)`;
          }
        } else {
          explanation = 'Food and dining establishments';
        }
        break;

      case 'shop':
      case 'shopping':
        if (subcategory) {
          const validation = await this.taginfo.validateTag('shop', subcategory);
          if (validation.valid) {
            tags.shop = [subcategory];
            explanation = `${subcategory} shops`;
          } else if (validation.suggestion) {
            tags.shop = [validation.suggestion];
            explanation = `${validation.suggestion} shops (suggested alternative to "${subcategory}")`;
          } else {
            const commonShops = await this.taginfo.getCommonShops(10);
            tags.shop = commonShops;
            explanation = `Common shop types (unknown type "${subcategory}")`;
          }
        } else {
          const commonShops = await this.taginfo.getCommonShops(15);
          tags.shop = commonShops;
          explanation = `Common shop types: ${commonShops.slice(0, 5).join(', ')}, etc.`;
        }
        break;

      case 'tourism':
      case 'tourist':
      case 'attraction':
        if (subcategory) {
          const validation = await this.taginfo.validateTag('tourism', subcategory);
          if (validation.valid) {
            tags.tourism = [subcategory];
            explanation = `Tourism: ${subcategory}`;
          } else {
            const commonTourism = await this.taginfo.getCommonTourism(10);
            tags.tourism = commonTourism;
            explanation = `Common tourism types (unknown type "${subcategory}")`;
          }
        } else {
          const commonTourism = await this.taginfo.getCommonTourism(10);
          tags.tourism = commonTourism;
          explanation = `Tourism and attractions: ${commonTourism.slice(0, 3).join(', ')}, etc.`;
        }
        break;

      case 'amenity':
        if (subcategory) {
          const validation = await this.taginfo.validateTag('amenity', subcategory);
          if (validation.valid) {
            tags.amenity = [subcategory];
            explanation = `Amenity: ${subcategory}`;
          } else {
            const commonAmenities = await this.taginfo.getCommonAmenities(10);
            tags.amenity = commonAmenities;
            explanation = `Common amenities (unknown type "${subcategory}")`;
          }
        } else {
          const commonAmenities = await this.taginfo.getCommonAmenities(15);
          tags.amenity = commonAmenities;
          explanation = `Common amenities: ${commonAmenities.slice(0, 5).join(', ')}, etc.`;
        }
        break;

      default: {
        // Try to detect if it's a specific amenity, shop, or tourism type
        const amenityValidation = await this.taginfo.validateTag('amenity', category);
        const shopValidation = await this.taginfo.validateTag('shop', category);
        const tourismValidation = await this.taginfo.validateTag('tourism', category);

        if (amenityValidation.valid) {
          tags.amenity = [category];
          explanation = `Amenity: ${category}`;
        } else if (shopValidation.valid) {
          tags.shop = [category];
          explanation = `Shop: ${category}`;
        } else if (tourismValidation.valid) {
          tags.tourism = [category];
          explanation = `Tourism: ${category}`;
        } else {
          // Fallback to common amenities
          const commonAmenities = await this.taginfo.getCommonAmenities(10);
          tags.amenity = commonAmenities;
          explanation = `Unknown category "${category}", showing common amenities`;
        }
      }
    }

    const query = this.buildOverpassQuery('node', tags, options);
    
    return {
      query,
      explanation,
      tags,
      source: 'Taginfo-enhanced query'
    };
  }

  /**
   * Get tag suggestions for autocomplete
   */
  async getTagSuggestions(input: string, limit = 10) {
    return this.taginfo.getTagSuggestions(input, limit);
  }

  /**
   * Build an Overpass QL query
   */
  private buildOverpassQuery(
    elementType: 'node' | 'way' | 'relation',
    tags: Record<string, string[]>,
    options: SmartQueryOptions
  ): string {
    const { bbox, around, limit = 100 } = options;
    
    let query = '[out:json][timeout:25];\n(\n';
    
    for (const [key, values] of Object.entries(tags)) {
      const valuePattern = values.length === 1 ? values[0] : `^(${values.join('|')})$`;
      
      if (bbox) {
        query += `  ${elementType}["${key}"~"${valuePattern}"](${bbox.south},${bbox.west},${bbox.north},${bbox.east});\n`;
      } else if (around) {
        query += `  ${elementType}["${key}"~"${valuePattern}"](around:${around.radius},${around.lat},${around.lon});\n`;
      } else {
        query += `  ${elementType}["${key}"~"${valuePattern}"];\n`;
      }
    }
    
    query += ');\n';
    query += `out body ${limit};\n`;
    query += '>;\n';
    query += 'out skel qt;';
    
    return query;
  }
} 