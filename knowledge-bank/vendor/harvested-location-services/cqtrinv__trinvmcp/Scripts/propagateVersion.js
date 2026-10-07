#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Get current directory in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Updates the version in both manifest.json and src/index.ts with the version from package.json
 */
function updateManifestVersion() {
    try {
        // Read package.json
        const packageJsonPath = path.join(process.cwd(), 'package.json');
        if (!fs.existsSync(packageJsonPath)) {
            console.error('❌ package.json not found in current directory');
            process.exit(1);
        }

        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        const version = packageJson.version;

        if (!version) {
            console.error('❌ No version found in package.json');
            process.exit(1);
        }

        console.log(`📦 Found version ${version} in package.json`);

        let updatedFiles = [];

        // Update manifest.json
        const manifestJsonPath = path.join(process.cwd(), 'manifest.json');
        if (fs.existsSync(manifestJsonPath)) {
            const manifestJson = JSON.parse(fs.readFileSync(manifestJsonPath, 'utf8'));
            const oldManifestVersion = manifestJson.version;
            
            manifestJson.version = version;
            fs.writeFileSync(manifestJsonPath, JSON.stringify(manifestJson, null, 2) + '\n');
            
            console.log(`✅ Updated manifest.json version from ${oldManifestVersion || 'undefined'} to ${version}`);
            updatedFiles.push('manifest.json');
        } else {
            console.log('⚠️  manifest.json not found, skipping');
        }

        // Update src/index.ts
        const indexTsPath = path.join(process.cwd(), 'src', 'index.ts');
        if (fs.existsSync(indexTsPath)) {
            let indexTsContent = fs.readFileSync(indexTsPath, 'utf8');
            
            // Pattern to match version declarations (supports various formats)
            const versionPatterns = [
                // export const VERSION = "1.0.0";
                /(export\s+const\s+VERSION\s*=\s*['"`])([^'"`]+)(['"`];?)/g,
                // const VERSION = "1.0.0";
                /(const\s+VERSION\s*=\s*['"`])([^'"`]+)(['"`];?)/g,
                // export const version = "1.0.0";
                /(export\s+const\s+version\s*=\s*['"`])([^'"`]+)(['"`];?)/g,
                // const version = "1.0.0";
                /(const\s+version\s*=\s*['"`])([^'"`]+)(['"`];?)/g,
            ];

            let foundVersion = false;
            let oldIndexVersion = null;

            for (const pattern of versionPatterns) {
                const match = indexTsContent.match(pattern);
                if (match) {
                    oldIndexVersion = match[0].match(/['"`]([^'"`]+)['"`]/)?.[1];
                    indexTsContent = indexTsContent.replace(pattern, `$1${version}$3`);
                    foundVersion = true;
                    break;
                }
            }

            if (foundVersion) {
                fs.writeFileSync(indexTsPath, indexTsContent);
                console.log(`✅ Updated src/index.ts version from ${oldIndexVersion || 'undefined'} to ${version}`);
                updatedFiles.push('src/index.ts');
            } else {
                console.log('⚠️  No version constant found in src/index.ts. Expected format: const VERSION = "1.0.0"; or export const VERSION = "1.0.0";');
            }
        } else {
            console.log('⚠️  src/index.ts not found, skipping');
        }

        if (updatedFiles.length === 0) {
            console.log('❌ No files were updated');
            process.exit(1);
        } else {
            console.log(`🎉 Successfully updated ${updatedFiles.length} file(s): ${updatedFiles.join(', ')}`);
        }

    } catch (error) {
        if (error.code === 'ENOENT') {
            console.error('❌ File not found:', error.path);
        } else if (error instanceof SyntaxError) {
            console.error('❌ Invalid JSON format:', error.message);
        } else {
            console.error('❌ Error updating files:', error.message);
        }
        process.exit(1);
    }
}

// Check if this script is being run directly (ES modules equivalent of require.main === module)
const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
    updateManifestVersion();
}

export default updateManifestVersion;