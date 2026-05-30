# Contributing to AI Recruitment System

Thank you for considering contributing to this project.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Tesseract OCR (`winget install UB-Mannheim.TesseractOCR` on Windows)
- Poppler for PDF rendering (`winget install oschwartz10612.poppler`)
- Git

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/shrs425p/AI-Recruitment-System.git
cd AI-Recruitment-System

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 3. Install runtime dependencies
pip install -r requirements.txt

# 4. Install development dependencies
pip install -r requirements-dev.txt

# 5. Install pre-commit hooks
pre-commit install

# 6. Run the test suite
pytest
```

## Development Workflow

1. **Branch** — create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Code** — make your changes. Follow the code style described below.
3. **Test** — add or update tests in `tests/`.
4. **Lint** — pre-commit runs automatically on `git commit`. You can also run it manually:
   ```bash
   ruff check . --fix
   ruff format .
   ```
5. **Commit** — use [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: add resume deduplication
   fix: handle empty PDF output in OCR fallback
   docs: update provider setup guide
   refactor: simplify provider router key validation
   ```
6. **Pull Request** — open a PR against `main` and fill in the PR template.

## Code Style

- **Formatter / Linter**: [Ruff](https://docs.astral.sh/ruff/) — configured in `pyproject.toml`.
- **Line length**: 120 characters.
- **Docstrings**: Google style for public functions and classes.
- **Type hints**: required for all new public functions.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=src --cov-report=term-missing

# Run a specific file
pytest tests/test_config.py -v
```

Tests live in `tests/`. Each module in `app/` and `src/` should have a corresponding `test_<module>.py`.

## Project Structure

```
AI-Recruitment-System/
├── app/                  # Flask application (routes, templates, static)
├── src/                  # Core business logic (NLP, ranking, OCR, AI)
├── config/               # Central configuration (config.py)
├── data/                 # Runtime data (gitignored)
├── docs/                 # Markdown documentation
├── models/               # Local ML models (Tesseract, Haar cascade)
├── notebooks/            # Jupyter notebooks for experimentation
├── scripts/              # Startup and utility scripts
├── tests/                # Test suite
├── main.py               # Application entry point (pywebview + Flask)
└── pyproject.toml        # Project metadata, ruff, pytest config
```

## Reporting Issues

Use the [GitHub issue tracker](https://github.com/shrs425p/AI-Recruitment-System/issues).
For security issues, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
