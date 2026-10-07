/**
 * Saved Orders Manager
 * Persists order recipes to localStorage for recall.
 * Pure CRUD - no dependencies on other modules.
 */

const STORAGE_KEY = 'countymap_saved_orders';

/**
 * Get all saved orders from localStorage.
 * @returns {Array} Array of saved order objects
 */
export function getAll() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch (error) {
    console.error('[SavedOrders] Failed to load:', error);
    return [];
  }
}

/**
 * Save an order with a name.
 * If a name already exists, it will be updated.
 * @param {string} name - Name for the saved order
 * @param {Array} items - Order items array
 * @param {string} summary - Order summary text
 * @param {Object} [options] - Optional { hints, map_state }
 * @returns {Object|null} The saved order object, or null if invalid
 */
export function save(name, items, summary, options = {}) {
  if (!items || items.length === 0) {
    console.warn('[SavedOrders] No items to save');
    return null;
  }

  const orders = getAll();

  // Check for duplicate name
  const existingIndex = orders.findIndex(o => o.name === name);

  const savedOrder = {
    id: 'order_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8),
    name: name,
    items: JSON.parse(JSON.stringify(items)),
    summary: summary || '',
    hints: options.hints || {},
    map_state: options.map_state || null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };

  if (existingIndex >= 0) {
    // Update existing
    savedOrder.id = orders[existingIndex].id;
    savedOrder.created_at = orders[existingIndex].created_at;
    orders[existingIndex] = savedOrder;
    console.log('[SavedOrders] Updated:', name);
  } else {
    // Add new
    orders.push(savedOrder);
    console.log('[SavedOrders] Created:', name);
  }

  persist(orders);
  return savedOrder;
}

/**
 * Load a saved order by name or id.
 * @param {string} nameOrId - Name or ID of the order to load
 * @returns {Object|null} The saved order or null if not found
 */
export function load(nameOrId) {
  const orders = getAll();
  const order = orders.find(o => o.name === nameOrId || o.id === nameOrId);

  if (!order) {
    console.warn('[SavedOrders] Not found:', nameOrId);
    return null;
  }

  console.log('[SavedOrders] Loaded:', order.name);
  return order;
}

/**
 * Delete a saved order by name or id.
 * @param {string} nameOrId - Name or ID of the order to delete
 * @returns {boolean} True if deleted, false if not found
 */
export function deleteOrder(nameOrId) {
  const orders = getAll();
  const index = orders.findIndex(o => o.name === nameOrId || o.id === nameOrId);

  if (index < 0) {
    console.warn('[SavedOrders] Not found for deletion:', nameOrId);
    return false;
  }

  const deleted = orders.splice(index, 1)[0];
  persist(orders);
  console.log('[SavedOrders] Deleted:', deleted.name);
  return true;
}

/**
 * Get names of all saved orders (useful for LLM context).
 * @returns {Array<string>} Array of saved order names
 */
export function getNames() {
  return getAll().map(o => o.name);
}

/**
 * Get statistics about saved orders.
 * @returns {Object} { count, names, totalItems }
 */
export function getStats() {
  const orders = getAll();
  return {
    count: orders.length,
    names: orders.map(o => o.name),
    totalItems: orders.reduce((sum, o) => sum + (o.items?.length || 0), 0)
  };
}

/**
 * Clear all saved orders.
 */
export function clearAll() {
  localStorage.removeItem(STORAGE_KEY);
  console.log('[SavedOrders] Cleared all');
}

/**
 * Persist orders array to localStorage.
 * @param {Array} orders - Orders array to save
 */
function persist(orders) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
  } catch (error) {
    console.error('[SavedOrders] Failed to persist:', error);
  }
}
