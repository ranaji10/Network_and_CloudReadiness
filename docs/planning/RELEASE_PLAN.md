# Release plan

## Versioning

- Semantic versioning. The version lives in `pyproject.toml` and `src/readiness/__init__.py`
  (`__version__`) and is printed in every report as `tool_version`, so a client report can always be
  traced to the code that produced it.
- Scoring domains and profiles carry their own `version` field. Bump a domain or profile version
  when weights, points or thresholds change, because that changes scores for the same documents.
- Patch: fixes, signal tweaks that do not change points. Minor: new checks, new adapters, new
  surfaces. Major: report schema or API changes that break consumers.

## Environments

| Environment | Terraform | Purpose | Who deploys |
|---|---|---|---|
| local | none (`docker compose`, `make serve`) | development, offline demos | anyone |
| dev | `infra/terraform/gcp/envs/dev.tfvars` | first cloud target; Cloud Build deploys on push to `main` with `_DEPLOY=true` | Cloud Build |
| staging | `envs/staging.tfvars` (INF-07) | release candidates, client pilots with synthetic data | Cloud Build on tag `v*-rc*` |
| prod | `envs/prod.tfvars` (INF-07), separate project | client assessments | Cloud Build on tag `v*` after manual approval |

Until INF-07 is done there is only dev; treat it as non-production and never run real client data
through it with egress enabled.

## Release checklist

1. `make check` and `make secrets-scan` green locally.
2. Tracker: every story in the release is `done`; `make tracker` run.
3. Version bumped in `pyproject.toml` and `__init__.py`; `uv lock` refreshed if dependencies moved.
4. Domain and profile versions bumped where scoring changed, with a line in `CHANGELOG.md`
   (create it at the first tagged release) saying what moved and why.
5. Run the synthetic demo (`make demo`) and compare the scores with the previous release; explain
   any change.
6. Tag `vX.Y.Z` on `main`. Cloud Build builds and pushes `IMAGE:<sha>`.
7. Deploy to the target environment (Cloud Build with `_DEPLOY=true`, or
   `gcloud run deploy --image IMAGE:<sha>`). Check `/healthz` and run one assessment with the
   synthetic pack through the API.
8. Record the deployed image digest and the Cloud Run revision name in the release notes.

## Rollback

Cloud Run keeps previous revisions. To roll back:

```
gcloud run services update-traffic readiness-api --region <region> --to-revisions <previous-revision>=100
```

Terraform ignores the image on the Cloud Run service, so a rollback by traffic split does not drift
the state. If a release changed Terraform resources, `terraform apply` the previous tag's `infra/`.

Reports are immutable per run id, so a rollback never changes an already produced report; re-run
the assessment on the rolled-back version if a client needs a corrected report.
