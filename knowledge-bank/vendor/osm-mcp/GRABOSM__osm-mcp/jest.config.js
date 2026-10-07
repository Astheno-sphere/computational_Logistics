export default {
  // Test environment
  testEnvironment: 'node',
  
  // Test file patterns
  testMatch: [
    '**/tests/**/*.test.{js,ts}',
    '**/src/**/__tests__/**/*.{js,ts}',
    '**/src/**/*.test.{js,ts}'
  ],
  
  // Setup files
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
  
  // Coverage configuration
  collectCoverage: false, // Disable coverage for now to focus on test functionality
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html', 'json'],
  collectCoverageFrom: [
    'dist/**/*.js',
    '!dist/**/*.test.js',
    '!dist/**/*.d.ts'
  ],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50
    }
  },
  
  // Test timeout
  testTimeout: 30000,
  
  // Module file extensions
  moduleFileExtensions: ['js', 'json', 'ts'],
  
  // Verbose output
  verbose: true,
  
  // Clear mocks automatically
  clearMocks: true,
  
  // Force exit after tests complete
  forceExit: true,
  
  // Detect open handles
  detectOpenHandles: true
}; 