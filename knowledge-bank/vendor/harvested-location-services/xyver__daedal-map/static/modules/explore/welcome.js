import { buildExploreWelcomeStatusMessage } from '../shared/surface-messaging.js';

export function buildExploreWelcomeMessage() {
  return (
    'Welcome to Explore. Start here when you want context: see a place, compare layers, ' +
    'and move around the map until a question becomes clear.<br><br>' +
    'The starter tray opens with earthquakes for live event motion, demographics for ' +
    'choropleth comparison, and temperature for climate graphics. Ask me about disasters, ' +
    'climate, population, and other maintained global data. Good first asks are "show me earthquakes ' +
    'near Japan", "compare heat and population", or "load the wildfire view". Type "help" or "how do you work?" ' +
    'anytime for a full guide.<br><br>' +
    '<div class="welcome-action-row">' +
    '<button class="chat-action-btn" data-action="run-preset" data-preset-id="explore:disasters_2020_2025" data-mode="explore">Load 10-year disasters</button> ' +
    '<button id="tutorialToggleBtn" class="chat-action-btn tutorial-toggle-btn" data-action="tutorial-toggle" type="button" aria-pressed="false">Tutorial Off</button>' +
    '</div>'
  );
}

export { buildExploreWelcomeStatusMessage };
