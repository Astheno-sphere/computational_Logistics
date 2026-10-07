#!/usr/bin/env node

/**
 * Simple test script to verify the OpenStreetMap MCP server
 * Run with: node tests/test-server.js
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SERVER_PATH = join(__dirname, '../dist/index.js');

// Test messages to send to the server
const TEST_MESSAGES = [
  // Test 1: List tools
  {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/list',
  },
  
  // Test 2: Search for a location
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'search_location',
      arguments: {
        query: 'Singapore',
        limit: 1
      }
    }
  },
  
  // Test 3: Reverse geocode
  {
    jsonrpc: '2.0',
    id: 3,
    method: 'tools/call',
    params: {
      name: 'reverse_geocode',
      arguments: {
        lat: 1.2847,
        lon: 103.8595
      }
    }
  }
];

async function testServer() {
  console.log('🧪 Testing OpenStreetMap MCP Server');
  console.log('=====================================');
  
  // Check if server file exists
  try {
    const fs = await import('fs');
    if (!fs.existsSync(SERVER_PATH)) {
      console.error('❌ Server file not found. Please run "npm run build" first.');
      process.exit(1);
    }
  } catch (error) {
    console.error('❌ Error checking server file:', error.message);
    process.exit(1);
  }
  
  let testsPassed = 0;
  let testsTotal = TEST_MESSAGES.length;
  
  for (let i = 0; i < TEST_MESSAGES.length; i++) {
    const testMessage = TEST_MESSAGES[i];
    console.log(`\n🔍 Test ${i + 1}/${testsTotal}: ${testMessage.method}`);
    
    try {
      const result = await sendMessageToServer(testMessage);
      
      if (result.error) {
        console.log('❌ Error response:', result.error);
      } else {
        console.log('✅ Success');
        testsPassed++;
        
        // Show some result details
        if (testMessage.method === 'tools/list') {
          console.log(`   📊 Found ${result.tools?.length || 0} tools`);
        } else if (testMessage.method === 'tools/call') {
          console.log(`   📋 Response received`);
        }
      }
    } catch (error) {
      console.log('❌ Test failed:', error.message);
    }
  }
  
  console.log('\n📊 Test Results');
  console.log('================');
  console.log(`✅ Passed: ${testsPassed}/${testsTotal}`);
  console.log(`❌ Failed: ${testsTotal - testsPassed}/${testsTotal}`);
  
  if (testsPassed === testsTotal) {
    console.log('\n🎉 All tests passed! The server is working correctly.');
  } else {
    console.log('\n⚠️  Some tests failed. Check the error messages above.');
    console.log('   💡 Common issues:');
    console.log('   - Internet connection required for API calls');
    console.log('   - Rate limiting may cause delays');
    console.log('   - API services may be temporarily unavailable');
  }
}

function sendMessageToServer(message) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', [SERVER_PATH], {
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    let stdout = '';
    let stderr = '';
    
    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('close', (code) => {
      if (stderr && !stderr.includes('OpenStreetMap MCP server running')) {
        reject(new Error(`Server error: ${stderr}`));
        return;
      }
      
      try {
        // Parse the JSON response
        const lines = stdout.trim().split('\n');
        const responseLine = lines[lines.length - 1]; // Get the last line
        const response = JSON.parse(responseLine);
        resolve(response);
      } catch (error) {
        reject(new Error(`Failed to parse response: ${error.message}\nOutput: ${stdout}`));
      }
    });
    
    child.on('error', (error) => {
      reject(new Error(`Failed to start server: ${error.message}`));
    });
    
    // Send the test message
    child.stdin.write(JSON.stringify(message) + '\n');
    child.stdin.end();
    
    // Timeout after 30 seconds
    setTimeout(() => {
      child.kill();
      reject(new Error('Test timeout'));
    }, 30000);
  });
}

// Run the tests
if (import.meta.url === `file://${process.argv[1]}`) {
  testServer().catch(console.error);
}

export { testServer }; 