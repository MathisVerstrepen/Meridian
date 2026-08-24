# Meridian 1.7.13-beta

Meridian `1.7.13-beta` keeps newly streamed chat content visible as conversations move from temporary sessions to generated nodes and removes blank spacing from filtered model menus.

## Highlights

### Reliable Live Chat Updates

New conversations now remain reactive while their temporary chat session transitions to the generated node that owns the response.

- The first streamed assistant message appears when a temporary session is assigned its generated node.
- In-place updates to streamed message text now render immediately after that session transition.

### Continuous Model Search Results

Model dropdown results now stay consecutive while searching, navigating with the keyboard, and scrolling through the list.

- Filtered options no longer develop blank gaps after repeated query changes or scrolling, including selectors opened from a zoomed canvas.
- Subscription quick-jump controls continue to move directly to their provider section, and keyboard navigation keeps the active option visible.

## Self-Hosting and Upgrade Notes

Meridian `1.7.13-beta` is a non-breaking frontend fix with no database migration, new configuration keys, new secrets, dependency-file changes, API changes, or data conversion steps.

- Rebuild and redeploy the UI to apply the chat reactivity and model-menu fixes; the API requires no release-specific configuration or migration work.
- Existing conversations, model settings, and provider connections require no migration or manual updates.
