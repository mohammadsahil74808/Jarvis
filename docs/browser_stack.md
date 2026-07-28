# Browser Automation Stack
This document details the single browser automation stack used by J.A.R.V.I.S.

## The Browser Use Adapter
J.A.R.V.I.S. relies exclusively on the `jarvis.browser.browser_adapter` (Browser Use engine) to execute web automation and autonomous browser tasks. This engine encapsulates Playwright and provides the following critical advantages:

1. **Persistent Profiles**: Maintains active, persistent Firefox profiles to support complex logins and session memory.
2. **Session Reuse**: Avoids creating and tearing down browser windows unnecessarily, providing a faster and more seamless interaction layer.
3. **Autonomous Capabilities**: Directly hooks into the `browser-use` architecture, permitting higher-order tasks and reasoning without relying on separate manual Playwright scripts.

### Historical Context
Previously, J.A.R.V.I.S. contained three distinct browser automation modules (`actions/browser_agent.py`, `actions/browser_control.py`, and `actions/browser_use_action.py`). To avoid conflicts, reduce bugs, and standardize automation, the redundant modules have been removed.

All browser-related actions now route through the unified `browser_control` action via the `BrowserUseAdapter`.

