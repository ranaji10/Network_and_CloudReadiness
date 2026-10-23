## Story

<!-- e.g. ING-04. One story per PR. Link the tracker entry. -->

## Summary

<!-- What changed and why, in a few sentences. -->

## Checklist

- [ ] `make check` is green locally
- [ ] No client data, secrets, project ids, bucket names, e-mails or client names in the diff
- [ ] Behaviour changes are in `config/*.yaml`, not hard-coded in Python
- [ ] No cloud SDK import outside `src/readiness/adapters/`
- [ ] Mock LLM remains the default; egress flag untouched
- [ ] Tests added or updated
- [ ] Docs updated (architecture / security / runbook as applicable)
- [ ] Tracker story updated and `make tracker` run
