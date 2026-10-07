// Basic test to verify Jest setup
describe('🧪 Basic Test Setup', () => {
  test('should run basic assertions', () => {
    expect(1 + 1).toBe(2);
    expect('hello').toBe('hello');
    expect([1, 2, 3]).toHaveLength(3);
  });

  test('should handle async operations', async () => {
    const promise = Promise.resolve('success');
    await expect(promise).resolves.toBe('success');
  });

  test('should have access to global testUtils', () => {
    expect(global.testUtils).toBeDefined();
    expect(global.testUtils.coordinates).toBeDefined();
    expect(global.testUtils.coordinates.jakarta).toEqual({
      lat: -6.2088,
      lon: 106.8456
    });
  });

  test('should validate coordinate ranges', () => {
    const validateCoordinates = (lat, lon) => {
      if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        throw new Error('Invalid coordinates');
      }
      return true;
    };

    // Valid coordinates
    expect(() => validateCoordinates(-6.2088, 106.8456)).not.toThrow();
    
    // Invalid coordinates
    expect(() => validateCoordinates(91, 106.8456)).toThrow('Invalid coordinates');
    expect(() => validateCoordinates(-6.2088, 181)).toThrow('Invalid coordinates');
  });

  test('should validate bounding boxes', () => {
    const jakarta = global.testUtils.boundingBoxes.jakarta;
    
    expect(jakarta.south).toBeLessThan(jakarta.north);
    expect(jakarta.west).toBeLessThan(jakarta.east);
    expect(jakarta.south).toBeGreaterThanOrEqual(-90);
    expect(jakarta.north).toBeLessThanOrEqual(90);
    expect(jakarta.west).toBeGreaterThanOrEqual(-180);
    expect(jakarta.east).toBeLessThanOrEqual(180);
  });
}); 