# Documentation Index

This folder contains the operating and engineering documentation for AI Recruitment System. The root README is intentionally short; detailed guidance lives here by topic.

## Start Here

| Need | Read |
|---|---|
| Install and launch the app | [Getting Started](getting-started.md) |
| Understand the full hiring workflow | [Pipeline Guide](pipeline.md) |
| Configure login, AI, email, and ports | [Configuration](configuration.md) |
| Build a production installer | [Build and Deploy](build-and-deploy.md) |
| Fix a runtime or packaging error | [Troubleshooting](troubleshooting.md) |

## Documentation Map

| Document | Scope |
|---|---|
| [Architecture](architecture.md) | Runtime layout, modules, data paths, threading model |
| [Pipeline Guide](pipeline.md) | Upload, OCR, NLP, ranking, scheduling, interviews, reports, auto-pipeline |
| [Configuration](configuration.md) | Runtime config file, settings keys, environment variables |
| [AI Providers](ai-providers.md) | Ollama privacy mode and cloud provider setup |
| [Interview System](interview-system.md) | Tokens, candidate portal, voice mode, proctoring, transcripts |
| [Google Calendar](google-calendar.md) | OAuth credentials, authentication, event creation |
| [API Reference](api-reference.md) | Page routes and JSON endpoints |
| [Build and Deploy](build-and-deploy.md) | PyInstaller, Inno Setup, smoke testing, release output |
| [Theming](theming.md) | Theme tokens, palettes, pywebview window styling |
| [Troubleshooting](troubleshooting.md) | Common startup, OCR, AI, database, and installer issues |
| [Changelog](changelog.md) | Release history and planned work |

## Runtime Model

In development, the app reads project resources from the repository and writes runtime data under the repo. In packaged builds, resources are read from the installed application bundle, while mutable data is written to:

```text
%LOCALAPPDATA%\AI Recruitment System\
```

That split is deliberate. It keeps installers clean, prevents developer credentials from shipping, and allows each Windows user to have separate settings and data.

## Privacy Model

By default, AI inference is local through Ollama. Candidate resumes, interview transcripts, reports, and the SQLite database stay on the machine unless cloud providers, Google Calendar, or SMTP email are explicitly configured.
