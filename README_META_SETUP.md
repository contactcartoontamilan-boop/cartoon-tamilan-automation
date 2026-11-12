# Facebook Page + Instagram Creator publishing setup

## Account requirements
- Instagram must remain a Professional Creator or Business account.
- Link that Instagram account to the Facebook Page in Meta's account/Page settings.
- Use a Meta app and the official Instagram Graph API / Facebook Pages API.
- The app may need App Review / Advanced Access before publishing for accounts outside app roles.

## Permissions to review for your app
The exact permission set depends on the API login flow and current Meta app configuration. Common permissions include:
- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_posts` (Facebook Page publishing)

Check the current Meta documentation and App Dashboard before requesting permissions. Do not assume a token with one permission grants all publishing access.

## Environment variables
Set these in the Oracle server environment or GitHub Actions Secrets (never commit real values):
- `META_PAGE_ID`
- `META_PAGE_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`
- `META_GRAPH_VERSION` (optional; defaults to v23.0 in this starter)
- `DRY_RUN=true` initially
- `PUBLISH_FACEBOOK=false` initially
- `PUBLISH_INSTAGRAM=false` initially

`META_PAGE_ACCESS_TOKEN` must be a Page token that has the required Page and Instagram permissions. `INSTAGRAM_USER_ID` is the Instagram professional account ID returned by Meta's connected-account lookup, not the @username.

## Public media hosting
Instagram publishing requires `image_url` or `video_url` that Meta's servers can fetch over public HTTPS. A local file path, private server URL, localhost URL, or Google Drive preview page will not work as a direct media URL. Host only media you own or are licensed to use.

## Test sequence
1. Keep `DRY_RUN=true`.
2. Confirm the Facebook Page ID, Page token, and Instagram professional account ID securely.
3. Test with a harmless image you own and a private/internal test caption.
4. Set `DRY_RUN=false`, but keep both platform flags false until each platform has been tested.
5. Enable one platform at a time:
   - `PUBLISH_FACEBOOK=true`
   - `PUBLISH_INSTAGRAM=true`
6. Check the post in the platform app and inspect server logs.

## API notes
- Instagram image publishing: create `/{ig-user-id}/media` with `image_url` and `caption`, then `/{ig-user-id}/media_publish` with `creation_id`.
- Instagram Reels: create a media container with `media_type=REELS` and `video_url`; poll its status until ready; then call `media_publish`.
- Facebook Page text/link publishing: `/{page-id}/feed`.
- Facebook Page photo publishing: `/{page-id}/photos`.

API versions and permissions change. Verify current official Meta documentation before production deployment. Respect rate limits and platform content rules.
