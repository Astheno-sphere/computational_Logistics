'use strict';

function computeDensityFromSnapshot(snapshot, viewport = {}) {
  const width = viewport.width || viewport.viewportWidth || 1280;
  const height = viewport.height || viewport.viewportHeight || 720;
  const viewportArea = Math.max(1, width * height);
  const stats = walkSnapshot(snapshot);
  const renderedArea = Math.min(viewportArea, stats.renderedArea);

  return {
    density: renderedArea / viewportArea,
    renderedArea,
    viewportArea,
    textNodeCount: stats.textNodeCount,
    imageCount: stats.imageCount,
    nonEmptyContainerCount: stats.nonEmptyContainerCount,
  };
}

async function computeDensityFromPage(page) {
  return page.evaluate(() => {
    const viewportArea = Math.max(1, window.innerWidth * window.innerHeight);
    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let renderedArea = 0;
    let textNodeCount = 0;
    let imageCount = 0;
    let nonEmptyContainerCount = 0;

    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.nodeType === Node.TEXT_NODE) {
        if ((node.textContent || '').trim()) textNodeCount++;
        continue;
      }
      if (!(node instanceof Element)) continue;
      const rect = node.getBoundingClientRect();
      const style = window.getComputedStyle(node);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      const area = Math.max(0, rect.width) * Math.max(0, rect.height);
      if (area > 0 && (node.children.length > 0 || (node.textContent || '').trim())) {
        nonEmptyContainerCount++;
        renderedArea += area;
      }
      if (node.tagName === 'IMG' && area > 0) imageCount++;
    }

    renderedArea = Math.min(viewportArea, renderedArea);
    return {
      density: renderedArea / viewportArea,
      renderedArea,
      viewportArea,
      textNodeCount,
      imageCount,
      nonEmptyContainerCount,
    };
  });
}

function walkSnapshot(snapshot) {
  const root = snapshot && (snapshot.root || snapshot);
  const stats = {
    renderedArea: 0,
    textNodeCount: 0,
    imageCount: 0,
    nonEmptyContainerCount: 0,
  };

  function visit(node) {
    if (!node || typeof node !== 'object') return;
    const nodeName = String(node.nodeName || node.name || '').toLowerCase();
    const text = node.nodeValue || node.text || node.textContent || '';

    if (nodeName === '#text') {
      if (String(text).trim()) textCount(stats);
    } else {
      const rect = node.rect || node.bounds || node.boundingBox || null;
      const area = rectArea(rect);
      const children = node.children || [];
      const hasContent = String(text).trim() || children.length > 0;
      if (area > 0 && hasContent) {
        stats.nonEmptyContainerCount++;
        stats.renderedArea += area;
      }
      if (nodeName === 'img' && area > 0) stats.imageCount++;
    }

    for (const child of node.children || []) visit(child);
  }

  visit(root);
  return stats;
}

function rectArea(rect) {
  if (!rect) return 0;
  const width = rect.width !== undefined ? rect.width : Math.max(0, (rect.right || 0) - (rect.left || 0));
  const height = rect.height !== undefined ? rect.height : Math.max(0, (rect.bottom || 0) - (rect.top || 0));
  return Math.max(0, width) * Math.max(0, height);
}

function textCount(stats) {
  stats.textNodeCount++;
  stats.renderedArea += 1200;
}

module.exports = {
  computeDensityFromSnapshot,
  computeDensityFromPage,
};
