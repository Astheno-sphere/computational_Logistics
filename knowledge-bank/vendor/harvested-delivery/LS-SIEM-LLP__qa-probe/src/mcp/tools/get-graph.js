'use strict';

module.exports = {
  name: 'qa_probe_get_graph',
  description: 'Get the dependency graph showing which backend API routes each frontend route calls. Ask: "Which backend routes does /dashboard call?"',
  inputSchema: {
    type: 'object',
    properties: {
      route: {
        type: 'string',
        description: 'Optional: filter to a specific frontend route (e.g. "/dashboard"). Omit to get the full graph.',
      },
    },
  },
  async execute({ route } = {}, { graph }) {
    if (!graph) return { error: 'No graph available. Run qa-probe analyze first.' };

    if (route) {
      const routeData = graph.frontendRoutes && graph.frontendRoutes[route];
      if (!routeData) {
        const available = Object.keys(graph.frontendRoutes || {}).slice(0, 20).join(', ');
        return { error: `Route "${route}" not found in graph. Available: ${available}` };
      }
      return {
        route,
        component: routeData.component,
        authGuard: routeData.authGuard,
        requiredScopes: routeData.requiredScopes,
        apiCalls: routeData.apiCalls,
        featureFlag: graph.featureFlags && graph.featureFlags[route],
      };
    }

    return {
      meta: graph.meta,
      routeCount: Object.keys(graph.frontendRoutes || {}).length,
      backendRouteCount: Object.keys(graph.backendRoutes || {}).length,
      featureFlagCount: Object.keys(graph.featureFlags || {}).length,
      frontendRoutes: graph.frontendRoutes,
    };
  },
};
