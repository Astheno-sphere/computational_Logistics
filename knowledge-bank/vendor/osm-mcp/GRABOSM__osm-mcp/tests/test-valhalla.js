// Test script to check Valhalla isochrone functionality and save as GeoJSON
import axios from 'axios';
import fs from 'fs';
import path from 'path';

async function testValhalla() {
  const testLocation = {
    latitude: 19.999644,
    longitude: 73.78963
  };

  const contours = [
    { time: 5 },
    { time: 10 },
    { time: 15 }
  ];

  // Test with public Valhalla instance
  const publicValhallaUrl = 'https://valhalla1.openstreetmap.de';
  
  console.log('Testing Valhalla isochrone...');
  console.log(`Location: ${testLocation.latitude}, ${testLocation.longitude}`);
  console.log(`Contours: ${contours.map(c => `${c.time} min`).join(', ')}`);
  console.log(`Using public instance: ${publicValhallaUrl}\n`);

  try {
    const requestBody = {
      locations: [{ lat: testLocation.latitude, lon: testLocation.longitude }],
      costing: 'auto',
      contours: contours,
      polygons: true
    };

    const response = await axios.get(`${publicValhallaUrl}/isochrone`, {
      params: {
        json: JSON.stringify(requestBody)
      },
      timeout: 30000
    });

    console.log('✅ SUCCESS: Valhalla isochrone request succeeded!');
    console.log(`Response status: ${response.status}`);
    console.log(`Features returned: ${response.data.features?.length || 0}`);
    
    if (response.data.features && response.data.features.length > 0) {
      console.log('\nContour details:');
      response.data.features.forEach((feature, index) => {
        const contour = feature.properties?.contour;
        const metric = feature.properties?.metric;
        console.log(`  Contour ${index + 1}: ${contour} ${metric} (${feature.geometry.type})`);
      });
    }

    // Save as GeoJSON file
    const geojson = {
      type: 'FeatureCollection',
      features: response.data.features || [],
      properties: {
        center: {
          latitude: testLocation.latitude,
          longitude: testLocation.longitude
        },
        costing: 'auto',
        contours: contours,
        generated_at: new Date().toISOString(),
        source: 'Valhalla isochrone API'
      }
    };

    const outputPath = path.join(process.cwd(), 'valhalla-isochrone-example.geojson');
    fs.writeFileSync(outputPath, JSON.stringify(geojson, null, 2));
    console.log(`\n💾 GeoJSON saved to: ${outputPath}`);

    return true;
  } catch (error) {
    console.error('❌ FAILED: Valhalla isochrone request failed');
    if (error.response) {
      console.error(`Status: ${error.response.status}`);
      console.error(`Error: ${JSON.stringify(error.response.data, null, 2)}`);
    } else if (error.request) {
      console.error('Network error: Unable to reach Valhalla server');
    } else {
      console.error(`Error: ${error.message}`);
    }
    return false;
  }
}

testValhalla()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('Unexpected error:', error);
    process.exit(1);
  });

