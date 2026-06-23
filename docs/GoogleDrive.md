# Google Drive Integration for Self-Hosted Meridian

Meridian can connect to Google Drive as an external file provider. Drive files appear in the file explorer and can be selected like regular files, but Meridian stores only lightweight metadata until a file is previewed or used in a request.

When bytes are needed, Meridian downloads them into a temporary per-user cache under `data/user_files/<user_id>/.cache/external/google_drive/`. Cached bytes count against the user's storage quota until the cache TTL expires and cleanup removes them.

## Recommended Self-Hosted Setup

For self-hosted instances, prefer using Google OAuth **test users** instead of publishing the app for public production access.

Google Drive read access uses this sensitive OAuth scope:

```text
https://www.googleapis.com/auth/drive.readonly
```

Publishing an app that uses this scope requires Google's OAuth verification process. That process can take days or weeks and requires public branding, privacy policy, domain verification, justification, and sometimes follow-up review. For a private self-hosted Meridian instance, adding each intended Google account as a test user is usually simpler and more appropriate.

## Create Google Cloud Credentials

1. Go to `https://console.cloud.google.com/`.
2. Create or select a Google Cloud project.
3. Go to `APIs & Services` -> `Library`.
4. Search for `Google Drive API` and enable it.
5. Search for `Google Sheets API` and enable it. Meridian uses it to turn Google Sheets into model-readable Markdown instead of binary `.xlsx` files.
6. Go to `APIs & Services` -> `OAuth consent screen`.
7. Configure the consent screen if it does not already exist.
8. In `Data Access` or `Scopes`, add:

```text
https://www.googleapis.com/auth/drive.readonly
```

9. Keep the app in `Testing` mode for self-hosted use.
10. Add each Meridian user Google account under `Test users`.
11. Go to `APIs & Services` -> `Credentials`.
12. Click `Create Credentials` -> `OAuth client ID`.
13. Choose `Web application`.
14. Add the authorized redirect URI for your Meridian UI.

For local development:

```text
http://localhost:3000/settings?tab=google-drive
```

For a self-hosted domain:

```text
https://your-meridian-domain.example/settings?tab=google-drive
```

15. Copy the OAuth client ID and client secret.

## Google Sheets Export Behavior

Google Sheets are not cached as `.xlsx` files. Meridian reads them through the Google Sheets API and generates a `.md` file with one CSV block per sheet. This makes spreadsheet contents readable by AI models and preserves multiple tabs in one text file.

Example generated cache content:

````md
# Spreadsheet: Budget 2026

Exported from Google Sheets as Markdown with one CSV block per sheet.

## Sheet: Summary

```csv
Month,Revenue,Cost
Jan,12000,8000
```

## Sheet: Details

```csv
Item,Owner,Status
Hosting,Mathis,Active
```
````

The OAuth scope remains `https://www.googleapis.com/auth/drive.readonly`, but the Google Sheets API must be enabled in the same Google Cloud project.

## Configure Meridian

In your Meridian `config.toml`, add or update the `[google_drive]` section:

```toml
[google_drive]
GOOGLE_DRIVE_CLIENT_ID = "your-google-oauth-client-id"
GOOGLE_DRIVE_CLIENT_SECRET = "your-google-oauth-client-secret"
GOOGLE_DRIVE_REDIRECT_URI = "https://your-meridian-domain.example/settings?tab=google-drive"
GOOGLE_DRIVE_CACHE_TTL_HOURS = 24
```

For local development, use:

```toml
GOOGLE_DRIVE_REDIRECT_URI = "http://localhost:3000/settings?tab=google-drive"
```

The redirect URI must match exactly in both places:

- Google Cloud OAuth client `Authorized redirect URIs`
- Meridian `GOOGLE_DRIVE_REDIRECT_URI`

After changing configuration, restart Meridian.

## Connect Google Drive in Meridian

1. Log in to Meridian.
2. Open `Settings`.
3. Go to `Blocks` -> `Google Drive`.
4. Click `Connect Google Drive`.
5. Sign in with a Google account that is listed as a test user.
6. Approve the read-only Drive permission.

After connection, open the file explorer and select the `Google Drive` tab.

## Troubleshooting

### Error 403: access_denied

This usually means the Google account is not allowed to use the OAuth app while it is in testing mode.

Check that:

- The Google account is listed under `OAuth consent screen` -> `Test users`.
- The test user is added in the same Google Cloud project that owns `GOOGLE_DRIVE_CLIENT_ID`.
- The app is still in `Testing` mode.
- The Drive scope is declared on the OAuth consent screen.
- The Google Drive API and Google Sheets API are both enabled in the same Google Cloud project.

### Google shows a generic error page

Check that the redirect URI is exact and uses the `google-drive` tab value:

```text
https://your-meridian-domain.example/settings?tab=google-drive
```

Avoid using a redirect URI with a space in the query parameter, such as `tab=google%20drive`. Google OAuth's unverified-app warning flow can fail on that form.

Also try:

- Restarting Meridian after changing `config.toml`.
- Using a private/incognito browser window.
- Signing in with only the intended Google test account.
- Disabling browser extensions for the OAuth attempt.
- Trying a personal Gmail account if a Workspace admin blocks unverified apps.

### Redirect URI mismatch

Google requires an exact match. These are different values:

```text
http://localhost:3000/settings?tab=google-drive
https://localhost:3000/settings?tab=google-drive
https://your-domain.example/settings?tab=google-drive
https://your-domain.example/settings?tab=google%20drive
```

Use the same scheme, host, port, path, and query string in Google Cloud and Meridian.

### Google Workspace accounts

Company or school Google accounts can be blocked by organization policy even when added as test users. If this happens, either ask the Workspace administrator to trust the OAuth app or use a personal Gmail account.

## When to Publish the Google OAuth App

Only publish and submit for Google verification if your Meridian instance needs arbitrary Google users outside your test-user list.

Publishing with `drive.readonly` generally requires:

- A verified domain.
- A public homepage.
- A public privacy policy.
- Accurate app branding.
- A demo video showing the Drive flow.
- A clear explanation for why Meridian needs read-only Drive access.

For most private self-hosted deployments, keep the app in testing and manage access with test users.
