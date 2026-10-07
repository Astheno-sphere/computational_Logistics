// Script to convert GeoJSON isochrones to PNG with center marker
import fs from 'fs';
import { createCanvas } from 'canvas';

function geojsonToPng(geojsonPath, outputPath) {
  // Read GeoJSON file
  const geojson = JSON.parse(fs.readFileSync(geojsonPath, 'utf8'));
  
  // Extract center point
  const center = geojson.properties.center;
  const centerLat = center.latitude;
  const centerLon = center.longitude;
  
  // Extract features (isochrones)
  const features = geojson.features;
  
  // Calculate bounding box from all features
  let minLat = Infinity, maxLat = -Infinity;
  let minLon = Infinity, maxLon = -Infinity;
  
  features.forEach(feature => {
    if (feature.geometry.type === 'Polygon') {
      feature.geometry.coordinates[0].forEach(coord => {
        const [lon, lat] = coord;
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
        minLon = Math.min(minLon, lon);
        maxLon = Math.max(maxLon, lon);
      });
    }
  });
  
  // Add padding
  const latPadding = (maxLat - minLat) * 0.1;
  const lonPadding = (maxLon - minLon) * 0.1;
  minLat -= latPadding;
  maxLat += latPadding;
  minLon -= lonPadding;
  maxLon += lonPadding;
  
  // Canvas dimensions
  const width = 1200;
  const height = 1200;
  const canvas = createCanvas(width, height);
  const ctx = canvas.getContext('2d');
  
  // Helper function to convert lat/lon to pixel coordinates
  const project = (lat, lon) => {
    const x = ((lon - minLon) / (maxLon - minLon)) * width;
    const y = height - ((lat - minLat) / (maxLat - minLat)) * height; // Flip Y axis
    return { x, y };
  };
  
  // Draw background
  ctx.fillStyle = '#f5f5f5';
  ctx.fillRect(0, 0, width, height);
  
  // Draw isochrones (draw from largest to smallest so smaller ones appear on top)
  const sortedFeatures = [...features].sort((a, b) => 
    (b.properties.contour || 0) - (a.properties.contour || 0)
  );
  
  sortedFeatures.forEach(feature => {
    if (feature.geometry.type === 'Polygon') {
      const coordinates = feature.geometry.coordinates[0];
      const contour = feature.properties.contour;
      const color = feature.properties.fillColor || feature.properties.color || '#6abf40';
      
      // Draw polygon
      ctx.beginPath();
      const firstPoint = project(coordinates[0][1], coordinates[0][0]);
      ctx.moveTo(firstPoint.x, firstPoint.y);
      
      for (let i = 1; i < coordinates.length; i++) {
        const [lon, lat] = coordinates[i];
        const point = project(lat, lon);
        ctx.lineTo(point.x, point.y);
      }
      
      ctx.closePath();
      
      // Fill with semi-transparent color
      ctx.fillStyle = color + '80'; // Add alpha channel
      ctx.fill();
      
      // Draw border
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      
      // Add label
      if (coordinates.length > 0) {
        const labelPoint = project(coordinates[Math.floor(coordinates.length / 2)][1], 
                                   coordinates[Math.floor(coordinates.length / 2)][0]);
        ctx.fillStyle = '#333';
        ctx.font = 'bold 16px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`${contour} min`, labelPoint.x, labelPoint.y - 5);
      }
    }
  });
  
  // Draw center marker
  const centerPoint = project(centerLat, centerLon);
  
  // Draw marker circle
  ctx.beginPath();
  ctx.arc(centerPoint.x, centerPoint.y, 8, 0, 2 * Math.PI);
  ctx.fillStyle = '#ff0000';
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2;
  ctx.stroke();
  
  // Draw marker pin
  ctx.beginPath();
  ctx.moveTo(centerPoint.x, centerPoint.y);
  ctx.lineTo(centerPoint.x, centerPoint.y + 15);
  ctx.lineTo(centerPoint.x - 5, centerPoint.y + 10);
  ctx.closePath();
  ctx.fillStyle = '#ff0000';
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2;
  ctx.stroke();
  
  // Add title
  ctx.fillStyle = '#333';
  ctx.font = 'bold 24px Arial';
  ctx.textAlign = 'center';
  ctx.fillText('Isochrone Map', width / 2, 30);
  
  // Add subtitle
  ctx.font = '14px Arial';
  ctx.fillText(`Center: ${centerLat.toFixed(6)}, ${centerLon.toFixed(6)}`, width / 2, 55);
  
  // Add legend
  const legendY = height - 100;
  ctx.font = '12px Arial';
  ctx.textAlign = 'left';
  ctx.fillText('Legend:', 20, legendY);
  
  sortedFeatures.forEach((feature, index) => {
    const contour = feature.properties.contour;
    const color = feature.properties.fillColor || feature.properties.color || '#6abf40';
    const y = legendY + 20 + (index * 20);
    
    // Draw color box
    ctx.fillStyle = color + '80';
    ctx.fillRect(20, y - 10, 20, 15);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(20, y - 10, 20, 15);
    
    // Draw text
    ctx.fillStyle = '#333';
    ctx.fillText(`${contour} minutes`, 50, y);
  });
  
  // Save to file
  const buffer = canvas.toBuffer('image/png');
  fs.writeFileSync(outputPath, buffer);
  console.log(`✅ PNG saved to: ${outputPath}`);
  console.log(`   Image size: ${width}x${height}px`);
  console.log(`   Features rendered: ${features.length}`);
}

// Run the script
const geojsonPath = process.argv[2] || 'valhalla-isochrone-example.geojson';
const outputPath = process.argv[3] || 'valhalla-isochrone-example.png';

geojsonToPng(geojsonPath, outputPath);

