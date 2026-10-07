const axios = require('axios');

async function testIsochrone() {
  console.log('Testing isochrone fix...');
  
  try {
    const response = await axios.post('http://localhost:3001/api/osrm/isochrone', {
      center_longitude: 103.8198,
      center_latitude: 1.3521,
      max_duration_seconds: 1800, // 30 minutes
      profile: 'driving'
    });
    
    console.log('✅ Isochrone request successful!');
    console.log(`📊 Response summary:`);
    console.log(`   - Total points: ${response.data.total_points}`);
    console.log(`   - Reachable points: ${response.data.reachable_count}`);
    console.log(`   - Grid size: ${response.data.grid_size}`);
    console.log(`   - Profile: ${response.data.profile}`);
    console.log(`   - Max duration: ${response.data.max_duration_seconds} seconds`);
    
    // Check that we got results
    if (response.data.grid && response.data.grid.length > 0) {
      console.log(`✅ Grid data received with ${response.data.grid.length} points`);
      
      // Check that we have some reachable points
      const reachablePoints = response.data.grid.filter(point => point.reachable);
      console.log(`✅ Found ${reachablePoints.length} reachable points`);
      
      if (reachablePoints.length > 0) {
        console.log(`   - First reachable point: [${reachablePoints[0].coordinates[0]}, ${reachablePoints[0].coordinates[1]}] (${reachablePoints[0].duration}s)`);
      }
    } else {
      console.log('⚠️  No grid data received');
    }
    
    console.log('\n🎉 Isochrone 414 error fix appears to be working!');
    
  } catch (error) {
    console.error('❌ Isochrone test failed:', error.message);
    if (error.response) {
      console.error('   Status:', error.response.status);
      console.error('   Data:', error.response.data);
    }
  }
}

// Run the test
testIsochrone(); 