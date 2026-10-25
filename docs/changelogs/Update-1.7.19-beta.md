# Meridian 1.7.19-beta

Meridian `1.7.19-beta` adds automatic retries for temporary OpenRouter failures, clearer workspace navigation, and fixes for chat forks, text input sizing, and model pinning.

## Highlights

### More Resilient OpenRouter Requests

- Retry temporary provider errors and connection failures with bounded backoff, up to four attempts, and respect `Retry-After` within a 90-second total wait cap.
- Show retry status in chat messages and text-to-text graph nodes. Cancelling generation also interrupts the retry wait.
- Stop retrying once a response has started producing content, and do not repeat completed tool rounds. Permanent errors fail immediately; temporary in-flight budget errors retry only when the provider supplies `Retry-After`.

### Clearer Workspace Navigation

- Show workspace names in the sidebar switcher instead of unlabeled dots, with the active workspace highlighted.
- Jump to the first nine workspaces with Alt+1 through Alt+9, or move between adjacent workspaces with Alt+PageUp and Alt+PageDown.
- Ignore workspace shortcuts while typing in input fields and prevent repeated or already-handled key events from switching workspaces.

### Chat and Model Selector Fixes

- Keep submission and streaming state attached to the chat that started generation, so forking during a reply does not make the fork appear busy or send updates to the wrong chat.
- Prevent failed background submissions from restoring input into a different active chat.
- Preserve the chat text input's parent height limit when the attachment collision popup appears.
- Pin models with Shift+Enter instead of Ctrl/Cmd+Shift+P, keeping the selector open with its query and focus intact. Ignore pin shortcuts during IME composition.

## Self-Hosting and Upgrade Notes

Meridian `1.7.19-beta` introduces no database migrations, new configuration keys, new secrets, or dependency changes. Existing stored data requires no conversion.

- Update matching frontend and API images to apply the navigation, chat, and provider changes.
- Review release PR CI and merge manually. Release automation does not deploy or restart production services.
