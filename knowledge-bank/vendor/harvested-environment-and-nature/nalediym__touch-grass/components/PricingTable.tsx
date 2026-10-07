import React from 'react';

const FREE_FEATURES = [
  'Weather + sunset nudges in every Claude Code session',
  'Streak tracking with longest-streak history',
  'All 4 MCP tools (conditions, activity, log, stats)',
  'Golden-hour activity suggestions',
  'Fully local — no accounts, no telemetry',
  'MIT open source',
];

const SUPPORTER_FEATURES = [
  'Everything in Free',
  'Your name in the README supporters section',
  'Priority GitHub issues',
  'Custom activity list via ~/.touch-grass/config.json',
  'Early access to new features',
];

// Replace with your real Polar checkout link after creating the product
const POLAR_SUPPORTER_URL = 'https://polar.sh/nalediym';
const GITHUB_INSTALL_URL = 'https://github.com/nalediym/touch-grass#install';

export const PricingTable: React.FC = () => {
  return (
    <div className="py-12 bg-white">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
            Free forever. Support if you love it.
          </h2>
          <p className="mt-4 text-xl text-gray-600">
            touch-grass is open source. If it&apos;s helped you step away from the screen, consider supporting it.
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Free tier */}
          <div className="border border-gray-200 rounded-lg shadow-sm divide-y divide-gray-200">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900">Free</h3>
              <p className="mt-4">
                <span className="text-4xl font-extrabold text-gray-900">$0</span>
                <span className="text-base font-medium text-gray-500"> / forever</span>
              </p>
              <a
                href={GITHUB_INSTALL_URL}
                className="mt-8 block w-full bg-gray-800 border border-transparent rounded-md py-2 text-sm font-semibold text-white text-center hover:bg-gray-900"
              >
                Install from GitHub
              </a>
            </div>
            <div className="pt-6 pb-8 px-6">
              <h4 className="text-xs font-medium text-gray-900 uppercase tracking-wide">What&apos;s included</h4>
              <ul className="mt-6 space-y-4">
                {FREE_FEATURES.map((feature) => (
                  <li key={feature} className="flex space-x-3">
                    <svg className="flex-shrink-0 h-5 w-5 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm text-gray-500">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Supporter tier */}
          <div className="border border-green-200 rounded-lg shadow-sm divide-y divide-green-100 ring-2 ring-green-500">
            <div className="p-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">Supporter</h3>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  🌿 Keep it growing
                </span>
              </div>
              <p className="mt-4">
                <span className="text-4xl font-extrabold text-gray-900">$9</span>
                <span className="text-base font-medium text-gray-500"> one-time</span>
              </p>
              <a
                href={POLAR_SUPPORTER_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 block w-full bg-green-600 border border-transparent rounded-md py-2 text-sm font-semibold text-white text-center hover:bg-green-700"
              >
                Support on Polar
              </a>
            </div>
            <div className="pt-6 pb-8 px-6">
              <h4 className="text-xs font-medium text-gray-900 uppercase tracking-wide">What&apos;s included</h4>
              <ul className="mt-6 space-y-4">
                {SUPPORTER_FEATURES.map((feature) => (
                  <li key={feature} className="flex space-x-3">
                    <svg className="flex-shrink-0 h-5 w-5 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm text-gray-500">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
