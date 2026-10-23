# Runbook: client data or secret exposed

Applies when client documents, extracted text, reports, pseudonym maps or secrets landed somewhere they
must not be: git history, a public bucket, a ticket, a chat, an external model without approval.

## 0. Stop the spread (first 15 minutes)

- Git: do not push further. If already pushed, make the repository private if it is not, and tell the maintainer.
- Bucket or object: remove public access, then delete the object (all versions).
- Model: stop the deployment (`_DEPLOY=false`, scale Cloud Run to zero or set `READINESS_ALLOW_LLM_EGRESS=false` and redeploy).
- Secret: treat it as compromised regardless of exposure window.

## 1. Rotate

| Exposed | Action |
|---|---|
| `READINESS_API_TOKEN` | new secret version, redeploy, disable old version |
| Model API key | revoke at the provider, new key, new secret version |
| Service account key file | delete the key in IAM, prefer workload identity so none exists |
| Cloud credentials in Terraform state | rotate; state bucket is private and versioned, review access logs |

## 2. Purge git history (if committed)

```bash
pip install git-filter-repo
git filter-repo --invert-paths --path <path-to-file>          # or --replace-text for a string
git push --force --all && git push --force --tags              # the one allowed force push; coordinate first
```

Everyone re-clones. GitHub support may be needed to drop cached views of the old objects. Confirm with
`make secrets-scan` and `git log --all -- <path>`.

## 3. Assess and notify

- What data, whose, how long exposed, who could have accessed it (bucket/ repo access logs, model provider retention).
- Notify the client contact per the engagement agreement; notify the security owner; legal if personal data is involved.

## 4. Record and prevent

- Add a story in the `GRD` epic with the root cause and the fix (a new redaction rule, a new `check_no_client_data` pattern, a process change).
- Add the pattern to `.gitleaks.toml` or `config/redaction.yaml` with a test.
- Update `docs/security/THREAT_MODEL.md` if a new threat was found.

Do not write client names, data samples or secret values into the story, the ADR or this runbook.
