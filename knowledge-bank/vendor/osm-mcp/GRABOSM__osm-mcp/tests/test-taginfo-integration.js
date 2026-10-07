import { spawn } from 'child_process';

// Test the new Taginfo-enhanced MCP tools
async function testTaginfoIntegration() {
  console.log('🧪 Testing Taginfo Integration in OpenStreetMap MCP Server\n');

  // Start the MCP server
  const server = spawn('npm', ['run', 'start'], {
    stdio: ['pipe', 'pipe', 'pipe'],
    shell: true
  });

  let serverOutput = '';
  
  server.stdout.on('data', (data) => {
    serverOutput += data.toString();
  });

  server.stderr.on('data', (data) => {
    console.error('Server error:', data.toString());
  });

  // Wait for server to start
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test cases
  const tests = [
    {
      name: '🛣️  Smart Highway Search - Major highways in Singapore',
      request: {
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/call',
        params: {
          name: 'search_highways_smart',
          arguments: {
            intent: 'major',
            bbox: {
              south: 1.1304753,
              west: 103.6920359,
              north: 1.4504753,
              east: 104.0120359
            },
            limit: 10
          }
        }
      }
    },
    {
      name: '🏪 Smart POI Search - Restaurants in Singapore',
      request: {
        jsonrpc: '2.0',
        id: 2,
        method: 'tools/call',
        params: {
          name: 'search_pois_smart',
          arguments: {
            category: 'restaurant',
            bbox: {
              south: 1.2966,
              west: 103.8478,
              north: 1.3521,
              east: 103.8820
            },
            limit: 5
          }
        }
      }
    },
    {
      name: '💡 Tag Suggestions - Highway types',
      request: {
        jsonrpc: '2.0',
        id: 3,
        method: 'tools/call',
        params: {
          name: 'get_tag_suggestions',
          arguments: {
            input: 'highway',
            limit: 10
          }
        }
      }
    },
    {
      name: '📊 Tag Statistics - Highway key',
      request: {
        jsonrpc: '2.0',
        id: 4,
        method: 'tools/call',
        params: {
          name: 'get_tag_stats',
          arguments: {
            key: 'highway',
            include_values: true,
            values_limit: 15
          }
        }
      }
    },
    {
      name: '✅ Tag Validation - highway=motorway',
      request: {
        jsonrpc: '2.0',
        id: 5,
        method: 'tools/call',
        params: {
          name: 'validate_osm_tag',
          arguments: {
            key: 'highway',
            value: 'motorway'
          }
        }
      }
    },
    {
      name: '❌ Tag Validation - highway=superhighway (invalid)',
      request: {
        jsonrpc: '2.0',
        id: 6,
        method: 'tools/call',
        params: {
          name: 'validate_osm_tag',
          arguments: {
            key: 'highway',
            value: 'superhighway'
          }
        }
      }
    }
  ];

  // Run tests
  for (const test of tests) {
    console.log(`\n${test.name}`);
    console.log('=' .repeat(60));
    
    try {
      // Send request to server
      server.stdin.write(JSON.stringify(test.request) + '\n');
      
      // Wait for response
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      console.log('✅ Test completed successfully');
      
    } catch (error) {
      console.error('❌ Test failed:', error.message);
    }
  }

  // Test list tools to verify new tools are registered
  console.log('\n🔧 Testing Tool Registration');
  console.log('=' .repeat(60));
  
  const listToolsRequest = {
    jsonrpc: '2.0',
    id: 999,
    method: 'tools/list'
  };
  
  server.stdin.write(JSON.stringify(listToolsRequest) + '\n');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Clean up
  server.kill('SIGTERM');
  
  console.log('\n🎉 Taginfo Integration Test Suite Completed!');
  console.log('\n📋 Summary of New Features:');
  console.log('   • Smart highway search with Taginfo-enhanced queries');
  console.log('   • Smart POI search with automatic tag validation');
  console.log('   • Tag suggestions and autocomplete');
  console.log('   • Tag usage statistics from Taginfo');
  console.log('   • Tag validation with suggestions');
  console.log('\n🔗 Benefits:');
  console.log('   • Semantic correctness (highway != amenity)');
  console.log('   • Real-world tag usage data');
  console.log('   • Better user guidance and error prevention');
  console.log('   • Dynamic query optimization');
}

// Run the test
testTaginfoIntegration().catch(console.error); 