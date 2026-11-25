# Production deployment

The backend image runs as a non-root user and is shared by two independently
supervised services:

- `api`: public HTTPS traffic; every background-job flag is forced off.
- `worker`: exactly one replica; scheduler, ingestion, push delivery and account
  deletion are enabled only after their migrations and provider acceptance pass.

Copy `production.env.example` to `production.env` outside version control. Put the
Firebase service-account JSON beside the compose file with mode `0600`. Terminate
TLS at a trusted reverse proxy and set `FORWARDED_ALLOW_IPS` to that proxy's exact
address or CIDR; never use `*` on an Internet-facing deployment.

Before enabling the worker, apply every numbered migration, run the staging
acceptance checklist, configure alerts for failed/stale jobs, and verify `/health/ready`.
Scale `api` independently. Never run more than one `worker` until ingestion has a
distributed lease and live multi-instance generation has passed acceptance.

The compose file is a reproducible reference. Hosted platforms may use the same
image with separate API and worker services and their own secret manager.

Host the files in `deploy/public/` at a stable HTTPS URL and set
`EXPO_PUBLIC_LEGAL_BASE_URL` to that directory before the production mobile build.
Verify the support mailbox and have local counsel review the policy text before
submitting the store listing. Configure the RevenueCat webhook endpoint as
`POST /api/v1/billing/revenuecat` with the exact bearer value stored in
`REVENUECAT_WEBHOOK_AUTH`.
