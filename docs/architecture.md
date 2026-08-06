# Architecture

AI Recruitment System is a Flask application presented as a Windows desktop app through pywebview. The backend is modular: routes handle UI/API behavior, engine modules perform recruitment tasks, and SQLite plus filesystem outputs store durable state.

## Layers

```text
pywebview desktop window
        |
Flask pages and JSON routes        app/routes/
        |
Recruitment engines                src/
        |
SQLite and pipeline files          app/database.py, data/output/
```

## Servers

Two Flask servers are started by `main.py`.

| Server | Default | Purpose |
|---|---|---|
| Desktop HTTP | `127.0.0.1:5001` | Local pywebview UI |
| Candidate HTTPS | `127.0.0.1:5000` | Candidate interview portal |

Ports are configurable with environment variables:

```bat
set ARS_DESKTOP_PORT=55321
set ARS_CANDIDATE_PORT=55322
set ARS_CANDIDATE_HOST=0.0.0.0
```

If a preferred port is busy, the app selects a free local port automatically.

## Important Paths

| Helper | Development | Packaged build |
|---|---|---|
| `resource_path()` | Repository root | PyInstaller resource directory |
| `install_path()` | Repository root | Installed app directory |
| `data_path()` | Repository `data/` | `%LOCALAPPDATA%\AI Recruitment System\data\` |

Packaged builds use local app data for mutable files so installers do not carry test credentials or user data.

## Folder Responsibilities

| Folder | Responsibility |
|---|---|
| `app/` | Flask app, templates, static assets, routes, rate limiting, database context manager |
| `src/` | OCR, NLP, ranking, scheduling, interview, reporting, provider logic |
| `config/` | Development config mirror only |
| `data/` | Runtime database, resumes, and pipeline outputs |
| `models/` | Bundled Tesseract and Vosk assets |
| `build/` | PyInstaller and Inno Setup configuration |
| `scripts/` | Pre-flight verifier, launch, build, setup, and maintenance helpers |
| `tests/` | Automated test suite (25 test cases) |
| `docs/` | Project documentation |

## Security & Database Architecture

- **Candidate API Rate Limiting**: `app/rate_limiter.py` provides thread-safe token bucket rate limiting for candidate endpoints (`/api/candidate/*`).
- **Global Error Handlers**: `app/__init__.py` registers global middleware for HTTP 400, 403, 404, 429, 500.
- **Database Context Management**: `app/database.py` uses `@contextmanager def db_session()` for auto-commit, error rollback, and connection cleanup. Connections use `PRAGMA WAL` and `PRAGMA busy_timeout = 10000`.

## Data Flow

```text
resumes -> text -> NLP JSON -> ranking -> schedule/tokens -> interview transcripts -> reports
```

Each stage writes files that the next stage reads. The database stores run metadata, candidate summaries, schedule rows, email logs, and interview tokens.

## Threading Model

| Thread | Purpose |
|---|---|
| Main thread | pywebview event loop |
| Desktop Flask thread | Local HR interface |
| Candidate Flask thread | HTTPS interview portal |
| Pipeline worker threads | Long-running OCR, NLP, ranking, scheduling, reporting |
| Proctoring thread | Webcam analysis during interviews |

Long-running work must run outside the request thread so the desktop UI stays responsive.
