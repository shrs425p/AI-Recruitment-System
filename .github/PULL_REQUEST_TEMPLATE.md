## Summary

<!-- Explain what changed and why. Keep it short, but give reviewers enough context. -->

## Change Type

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Refactor
- [ ] Build or deployment
- [ ] Test coverage

## Risk

- [ ] Low: isolated change, easy rollback
- [ ] Medium: touches shared behavior or build output
- [ ] High: changes data, auth, installer, or candidate interview flow

## Testing

<!-- List commands and manual checks actually completed. -->

- [ ] `venv\Scripts\python.exe -m ruff check .`
- [ ] `venv\Scripts\python.exe -m pytest`
- [ ] `venv\Scripts\python.exe -m compileall -q main.py app src tests`
- [ ] Packaged app smoke-tested, if build/runtime behavior changed

## Documentation

- [ ] README updated, if user-facing behavior changed
- [ ] Relevant `docs/` page updated
- [ ] `docs/changelog.md` updated

## Security and Data

- [ ] No secrets, API keys, tokens, resumes, interview data, or local config committed
- [ ] Installer does not bundle developer runtime config
- [ ] Any cloud-provider behavior is documented and opt-in

## Screenshots

<!-- Add before/after screenshots for UI changes. -->
