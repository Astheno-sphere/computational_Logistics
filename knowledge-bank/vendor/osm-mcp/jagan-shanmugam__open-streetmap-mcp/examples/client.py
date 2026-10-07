from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json

async def main():
    # Configure connection to the OSM MCP server
    server_params = StdioServerParameters(
        command="osm-mcp-server",
        args=[],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Get information about tools
            response = await session.list_tools()
            tools = response.tools
            print(f"Available tools: {[tool.name for tool in tools]}")
            
            # Example 1: Geocode a location (using a tool)
            print("\n--- Example 1: Geocode a Location ---")

            location_result = await session.call_tool(
                "geocode_address", 
                {"address": "San Francisco"}
            )
            
            # Parse the JSON response from the text content
            locations = []
            for content_item in location_result.content:
                if content_item.type == 'text':
                    locations.append(json.loads(content_item.text))
            
            if locations and len(locations) > 0:
                print(f"Found place: {locations[0].get('display_name', 'Unknown')}")
                lat = float(locations[0].get('lat', 0))
                lon = float(locations[0].get('lon', 0))
                print(f"Coordinates: {lat}, {lon}")
                
                # Example 2: Find nearby places
                print("\n--- Example 2: Find Nearby Places ---")
                nearby_result = await session.call_tool(
                    "find_nearby_places",
                    {
                        "latitude": lat,
                        "longitude": lon,
                        "radius": 500,
                        "categories": ["amenity"],
                        "limit": 10
                    }
                )
                
                # Parse the nearby places result
                nearby_places = {}
                if nearby_result.content and len(nearby_result.content) > 0:
                    nearby_text = nearby_result.content[0].text
                    nearby_places = json.loads(nearby_text)
                
                total_count = nearby_places.get('total_count', 0)
                print(f"Found {total_count} places near the location")
                
                # Print some categories if available
                categories = nearby_places.get('categories', {})
                for category, subcategories in categories.items():
                    print(f"Category: {category}")
                    for subcategory, places in subcategories.items():
                        print(f"  - {subcategory}: {len(places)} places")
                
                # Example 3: Explore an area
                print("\n--- Example 3: Explore Area ---")
                area_result = await session.call_tool(
                    "explore_area",
                    {
                        "latitude": lat,
                        "longitude": lon,
                        "radius": 800
                    }
                )
                
                # Parse the area exploration result
                area_info = {}
                if area_result.content and len(area_result.content) > 0:
                    area_text = area_result.content[0].text
                    area_info = json.loads(area_text)
                
                print(f"Area exploration complete!")
                print(f"Total features: {area_info.get('total_features', 0)}")
                for category, subcats in area_info.get('categories', {}).items():
                    if subcats:
                        feature_count = sum(len(places) for places in subcats.values())
                        print(f"  • {category}: {feature_count} features")

if __name__ == "__main__":
    asyncio.run(main())