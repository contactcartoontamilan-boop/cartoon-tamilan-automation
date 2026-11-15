# Oracle automatic deployment setup

The workflow in `.github/workflows/deploy-oracle.yml` deploys every push to
`feature/v14-social-publish-fb-ig-x-qa` to the existing isolated V14 checkout
on Oracle. The cron entry on Oracle already runs the scheduler once per minute,
so it loads the updated Python code on its next run.

Before the workflow can connect, add these two repository Actions secrets under
Settings → Secrets and variables → Actions:

- `ORACLE_HOST`: the Oracle VM public IP or DNS name.
- `ORACLE_SSH_KEY`: the complete private SSH key that can log in as
  `ubuntu`. Do not commit the private key or paste it into chat.

The deploy job fetches the pushed branch, updates the V14 checkout, installs
its pinned Python requirements, and checks that the scheduler modules compile.
It does not print or store the SSH key in the repository.

This only deploys code. The existing Meta environment variables on Oracle
remain on that VM. Live publishing still requires the existing explicit
platform and live-publish gates to remain enabled.
