# Meridian 1.7.11-beta

Meridian `1.7.11-beta` adds pluggable email delivery with AWS SES as an alternative to SMTP, makes graph handle targeting easier when zoomed out, and moves frontend linting from ESLint to oxlint with stricter runtime safety. This release has no database migration or data changes.

## Highlights

### Pluggable Email Delivery (SMTP and Amazon SES)

Verification email delivery is now pluggable and selected by `EMAIL_PROVIDER`. SMTP remains the default when the variable is unset or set to `smtp`; values are case-insensitive and surrounding whitespace is ignored.

- Set `EMAIL_PROVIDER=smtp` for SMTP delivery (default) or `EMAIL_PROVIDER=ses` for AWS SES v2 delivery. Only the selected provider is used; invalid provider values, incomplete selected-provider configuration, and delivery failures produce sanitized logs and Sentry reports with no cross-provider fallback or retry, avoiding duplicate sends.
- SES delivery uses `SES_REGION` and `SES_FROM_EMAIL` as required inputs and optional `SES_CONFIGURATION_SET_NAME` forwarded as `ConfigurationSetName` only when non-empty. The API creates a `sesv2` client for the explicit region and sends HTML verification content via `send_email`, offloading the blocking call with `asyncio.to_thread`.
- SES relies on the Boto3 default credential chain without passing credentials directly from application code; populated AWS environment credentials are checked before shared profile, web-identity, container-role, and instance-role sources. Failures in either provider are logged with sanitized messages (`configuration is incomplete; message was not sent` or `delivery failed; message was not sent`) without logging addresses, codes, or provider exception text, matching `api/app/services/email_service.py` and `api/tests/test_email_service.py`.

### Easier Graph Connections When Zoomed Out

Prompt, attachment, and context handles now keep a consistent pointer hit zone when the canvas is zoomed out.

- `ui/app/components/ui/graph/node/utils/handleCore.vue` now exports `getHandleHitZoneScale(zoom)` and `MAX_HANDLE_HIT_ZONE_SCALE = 3`, returning `1` for `zoom >= 1` or non-finite/non-positive values and `Math.min(1 / zoom, 3)` otherwise, so the hit zone scales inversely when zoomed out up to 3x.
- The shared `handleCore` drives `handlePrompt`, `handleAttachment`, and `handleContext` via `UiGraphNodeUtilsHandleCore` and applies the scale through `--handle-hit-zone-scale` on a `::before` pseudo-element (`transform: translate(-50%, -50%) scale(var(--handle-hit-zone-scale))`), leaving visible handle size and styles (`width`, `height`, `background`) unchanged and reacting to `useVueFlow().viewport.zoom`.
- Behavior is verified by `ui/tests/nuxt/handleCore.spec.ts`, which checks `1` at `1` and above, `2` at `0.5` zoom, capping at `3`, and that reactive viewport updates change only the CSS variable while visible styles stay intact.

### Frontend Tooling and Runtime Reliability

Frontend linting has moved from ESLint to oxlint as a reliability and tooling improvement rather than a product feature change.

- `ui/package.json` `lint` and `lint:fix` now run `oxlint .` and `oxlint . --fix`; `ui/eslint.config.mjs` was removed along with `eslint` and `@nuxt/eslint`, and `oxlint` with `@oxlint/plugins` plus `ui/oxlint.config.ts` were added. `ui/nuxt.config.ts` no longer registers `@nuxt/eslint`, and the Tailwind Vite plugin boundary now carries an explicit safety comment.
- `ui/oxlint.config.ts` enables `correctness` as error, registers `eslint`, `typescript`, `unicorn`, `oxc`, and `vue` plugins, and enforces custom `tools/oxlint/anti-slop` rules (`no-chained-type-assertions`, `no-widen-then-assert`, `no-unsafe-dictionary-type`, `no-unknown-parameters`, `no-unknown-returns`, `no-known-value-widening`, and `require-safety-comment-for-type-assertion`, among others).
- The change spans broad runtime validation replacing unsafe casts: many components, composables, stores, and utils now use `ui/app/utils/runtimeTypes.ts` and narrowed types instead of `as` assertions or `typeof` checks, improving type safety without adding new user-facing features.

## Self-Hosting and Upgrade Notes

Meridian `1.7.11-beta` is a non-breaking application update with no database migration, new tables, or data changes. Existing SMTP setups remain compatible without configuration changes.

- API dependency: `api/requirements.txt` adds `boto3` for SES. Rebuild the API image to include the new dependency; no migration or manual data step is required.
- SMTP compatibility: `email.provider` defaults to `smtp` in `docker/config/defaults/common.yaml` and is required in `docker/config/schema.yaml`. Deployments without `EMAIL_PROVIDER` set, or with `EMAIL_PROVIDER=smtp`, continue to use existing `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_AUTH_PROTOCOL`, and `SMTP_FROM_EMAIL` values with no action required.
- SES opt-in: to use SES set `EMAIL_PROVIDER=ses` and provide non-empty `SES_REGION` and `SES_FROM_EMAIL`; the sender address or its domain must be verified in the selected region, and `SES_CONFIGURATION_SET_NAME` must reference an existing configuration set in that region when set. The IAM principal needs `ses:SendEmail` for the sender identity. Accounts in the SES sandbox can send only to verified recipients or the SES mailbox simulator until AWS grants production access. Prefer workload, web-identity, container, or instance roles and short-lived credentials; alternatively set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` together and add `AWS_SESSION_TOKEN` for temporary credentials, keeping all three only in the mode `0600` profile secrets env file. Populated AWS env credentials take precedence over role sources, so remove stale values when switching to roles. Recreate or restart the API after changing any email or credential value.
- Configuration and compose forwarding: new settings `email.provider` (`EMAIL_PROVIDER`), `email.ses.region` (`SES_REGION`), `email.ses.from_email` (`SES_FROM_EMAIL`), `email.ses.configuration_set_name` (`SES_CONFIGURATION_SET_NAME`) and optional secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` are defined in `docker/config/schema.yaml`, defaulted in `docker/config/defaults/common.yaml` and `docker/config/overrides/local.example.yaml` / `production.example.yaml`, and forwarded to the API service in `docker/docker-compose.yml` and `docker/docker-compose.prod.yml`. `docker/tests/test_config.sh` and `docs/config.md` are updated to document provider selection, credential precedence, sandbox restrictions, and sanitized error handling.
- UI dependencies: developers and source builders must reinstall UI dependencies (`pnpm install`) because `ui/eslint.config.mjs` and ESLint dependencies were removed and `oxlint`, `@oxlint/plugins`, `ui/oxlint.config.ts`, and `tools/oxlint/anti-slop` were added; `ui/pnpm-lock.yaml` is updated accordingly. Frontend Docker builds should be rebuilt to include the oxlint configuration. `make lint` / `make lint-ui` now run oxlint.
