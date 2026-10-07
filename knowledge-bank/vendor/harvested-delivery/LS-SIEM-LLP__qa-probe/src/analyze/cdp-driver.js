'use strict';

const { computeDensityFromPage } = require('../probe/layout-density');

function createCdpDriver(runtimeConfig = {}) {
  let playwright;
  try {
    playwright = require('playwright');
  } catch (err) {
    throw new Error(
      'Runtime tracing requires the optional "playwright" dependency. ' +
      'Run npm install in qa-probe and ensure optional dependencies are installed.'
    );
  }

  const browserName = runtimeConfig.browser || 'chromium';
  const browserType = playwright[browserName];
  if (!browserType) {
    throw new Error(`Unsupported runtime browser: ${browserName}`);
  }

  let browserPromise = null;

  async function getBrowser() {
    if (!browserPromise) {
      browserPromise = browserType.launch({ headless: true });
    }
    return browserPromise;
  }

  return {
    async traceRoute(url, options = {}) {
      const browser = await getBrowser();
      const context = await browser.newContext({
        viewport: runtimeConfig.viewport || { width: 1280, height: 720 },
        ignoreHTTPSErrors: !!runtimeConfig.ignoreHTTPSErrors,
      });
      const page = await context.newPage();
      const requests = [];
      let domSnapshot = null;

      try {
        if (browserName === 'chromium') {
          const session = await context.newCDPSession(page);
          await session.send('Network.enable');
          session.on('Network.requestWillBeSent', event => {
            if (event && event.request) {
              requests.push({
                method: event.request.method || 'GET',
                url: event.request.url,
                resourceType: event.type || null,
              });
            }
          });

          await page.goto(url, {
            waitUntil: 'domcontentloaded',
            timeout: options.navigationTimeoutMs || runtimeConfig.navigationTimeoutMs || 30000,
          });
          await page.waitForTimeout(options.captureWindowMs || runtimeConfig.captureWindowMs || 5000);
          domSnapshot = await session.send('DOM.getDocument', { depth: -1, pierce: true });
        } else {
          page.on('request', request => {
            requests.push({
              method: request.method(),
              url: request.url(),
              resourceType: request.resourceType(),
            });
          });
          await page.goto(url, {
            waitUntil: 'domcontentloaded',
            timeout: options.navigationTimeoutMs || runtimeConfig.navigationTimeoutMs || 30000,
          });
          await page.waitForTimeout(options.captureWindowMs || runtimeConfig.captureWindowMs || 5000);
          domSnapshot = { html: await page.content() };
        }

        return { requests, domSnapshot };
      } finally {
        await context.close();
      }
    },

    async captureRoute(url, options = {}) {
      const browser = await getBrowser();
      const viewport = options.viewport || runtimeConfig.viewport || { width: 1280, height: 720 };
      const context = await browser.newContext({
        viewport,
        ignoreHTTPSErrors: !!runtimeConfig.ignoreHTTPSErrors,
      });
      const page = await context.newPage();

      try {
        await page.goto(url, {
          waitUntil: 'networkidle',
          timeout: options.navigationTimeoutMs || runtimeConfig.navigationTimeoutMs || 30000,
        });
        const density = await computeDensityFromPage(page);
        let screenshotPath = null;
        if (options.screenshotPath) {
          screenshotPath = options.screenshotPath;
          await page.screenshot({
            path: screenshotPath,
            fullPage: false,
          });
        }
        return { density, screenshotPath };
      } finally {
        await context.close();
      }
    },

    async close() {
      if (browserPromise) {
        const browser = await browserPromise;
        browserPromise = null;
        await browser.close();
      }
    },
  };
}

module.exports = { createCdpDriver };
