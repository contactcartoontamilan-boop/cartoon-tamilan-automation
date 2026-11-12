# CartoonTamilan Python + GitHub Automation

This project reads the CartoonTamilan RSS feed, creates bilingual Tamil/English promotional drafts, tracks processed items, and can optionally publish to a Facebook Page and Instagram Professional account through Meta APIs.

## Safe defaults
- `DRY_RUN=true`
- `PUBLISH_FACEBOOK=false`
- `PUBLISH_INSTAGRAM=false`

No real social post is sent with these defaults. Keep them until local tests and API permissions are verified.

## Repository layout
- `main.py`: RSS collection, captions, draft output, orchestration
- `config.yaml`: website and RSS sources
- `social/`: Facebook and Instagram publishing modules
- `data/state.json`: duplicate tracking
- `output/`: generated draft JSON files (created at runtime)
- `.github/workflows/daily.yml`: scheduled GitHub Actions workflow
- `.env.example`: names of environment variables; contains no credentials

## Local test (Termux / Linux)
```bash
pkg update -y
pkg install python git -y
pip install -r requirements.txt
cp .env.example .env
python main.py
```
On Termux, first clone this repository with:
```bash
git clone https://github.com/contactcartoontamilan-boop/cartoon-tamilan-automation.git
cd cartoon-tamilan-automation
```

## Meta setup
See [social/README_META_SETUP.md](social/README_META_SETUP.md). Store credentials only in GitHub Actions Secrets or Oracle environment variables. Never commit tokens or paste them into chat.

## GitHub Actions
The workflow is scheduled for 08:00 India time (02:30 UTC); scheduled starts may be delayed. You can also start it manually from the Actions tab. GitHub Actions has usage limits; it is not an unlimited hosting service.

## Current limitations
- RSS image extraction is best-effort; Instagram skips items without a publicly fetchable HTTPS image/video URL.
- Captions are templates, not AI-generated fact-checked news.
- YouTube, Pinterest, Threads, poster/video generation, and analytics are not implemented yet.
- Platform API permissions, quotas, review and policies apply. Verify Meta's current API version and requirements before production.
