# Changelog

All notable changes are documented here. This project follows semantic versioning where practical.

## Unreleased

### Added

- One-click Auto-Pipeline from the dashboard.
- Background progress tracking for the automatic pipeline.
- Pre-interview shortlist reports generated after ranking.
- Report generation as part of the automatic pipeline when interview transcripts exist.
- Health endpoint for packaged-app smoke testing.
- Focused tests for authentication, health, utilities, and Auto-Pipeline startup.

### Changed

- Runtime config is generated per user in local app data for packaged builds.
- Developer config is no longer bundled into the installer.
- Desktop and candidate ports can be configured by environment variable and fall back to free ports.
- Documentation has been split into focused topic files instead of a single oversized README.

### Fixed

- Packaged import crash caused by importing `APP_DATA_DIR` from the wrong module.
- Fresh installs no longer inherit development login credentials.
- Auto-Pipeline no longer blocks the HTTP request while long-running steps execute.
- Interview answers now use the real AI evaluation rubric instead of placeholder scores.
- Browser and answer-level proctoring flags are stored in interview transcripts.
- Scheduling now rejects duplicate or past slots and supports configurable candidate count.
- Candidate-facing network access can no longer reach HR screens or HR APIs by URL editing.
- Candidate interview APIs now require a private per-session key and matching client fingerprint.

## 1.0.0 - 2026-05-30

### Added

- Resume upload for PDF and image files.
- Text extraction with PyMuPDF and Tesseract OCR.
- AI resume parsing into structured candidate profiles.
- Candidate ranking against a job description.
- Scheduling with ICS generation and Google Calendar integration.
- Token-based candidate interview portal.
- Text and voice interview modes.
- Browser and webcam proctoring signals.
- AI-assisted report generation.
- Settings UI for AI, email, login, theme, and HR profile.
- PyInstaller folder build and Inno Setup installer.

## Planned

| Feature | Target |
|---|---|
| CSV/Excel exports | 1.1 |
| More configurable interview templates | 1.1 |
| Stronger analytics dashboard | 1.2 |
| Multi-user HR roles | 2.0 |
| Optional server deployment mode | 2.0 |
