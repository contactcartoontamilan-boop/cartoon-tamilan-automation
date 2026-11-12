# Facebook Page + Instagram Creator publishing setup

## Requirements
- Instagram must be a Professional Creator or Business account.
- Link Instagram to the Facebook Page.
- Use a Meta app and the official APIs; App Review/Advanced Access may be required.

## Common permissions to review
- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_posts`

Exact permissions depend on Meta's current login flow and app configuration.

## Environment variables
Set these as GitHub Actions Secrets or Oracle environment variables; never commit real values:
- `META_PAGE_ID`
- `META_PAGE_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`
- `META_GRAPH_VERSION`
- `DRY_RUN=true` initially
- `PUBLISH_FACEBOOK=false`
- `PUBLISH_INSTAGRAM=false`

Instagram requires a publicly fetchable HTTPS image or video URL. Local files and private URLs will not work.

## Safe test order
1. Keep `DRY_RUN=true`.
2. Validate credentials securely.
3. Test with media you own.
4. Only after review, set `DRY_RUN=false` and enable one platform at a time.

API versions and permissions change; verify current Meta documentation before production.
