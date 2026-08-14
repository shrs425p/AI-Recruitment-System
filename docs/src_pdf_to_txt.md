# Documentation for `pdf_to_txt.py`

**Path:** `src/pdf_to_txt.py`

## Module Docstring
No module-level docstring provided.

## Role
The `pdf_to_txt.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (extract_direct_text, clean_text, process_file) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `io`
- `logging`
- `re`
- `sys`
- `time`
- `pathlib.Path`
- `pymupdf`
- `pytesseract`
- `PIL.Image`
- `src.common.data_path`
- `src.common.install_path`

### Global Variables
- `logger`
- `logger`
- `_bundled_tesseract`
- `INPUT_FOLDER`
- `OUTPUT_FOLDER`
- `MIN_DIGITAL_TEXT_LENGTH`
- `WATCH_INTERVAL_SECONDS`

### Classes
No classes found.

### Functions
#### `extract_direct_text(pdf_path)`
**Docstring:** Extract embedded text from a digital PDF using PyMuPDF (pymupdf).

This is fast (~milliseconds) because it reads text already stored in the
PDF rather than running OCR.  Works for PDFs created by Word, LaTeX, etc.

Returns:
    str — extracted text (may be empty for scanned PDFs).

#### `clean_text(text)`
**Docstring:** Normalise raw extracted text so it is clean and consistent.

Steps:
  - Remove null bytes that can appear in some PDFs.
  - Normalise Windows-style line endings (\r\n → \n).
  - Collapse runs of 3+ blank lines into a single blank line
    (preserves paragraph breaks without excessive whitespace).
  - Collapse multiple spaces/tabs into a single space.

#### `process_file(file_path, output_path)`
**Docstring:** Convert a single PDF or image resume to a plain .txt file.

Logic:
  1. Skip if the output .txt already exists (idempotent — safe to re-run).
  2. For PDFs: try direct text extraction first; fall back to OCR if short.
  3. For images (PNG/JPG): always use OCR.
  4. Clean the extracted text.
  5. Skip saving if the result is empty (avoids blank files).
  6. Write the .txt file next to the other converted resumes.

Returns:
  True  — new file was processed and saved.
  False — file was skipped (already exists) or extraction yielded nothing.

#### `run_watcher()`
**Docstring:** Poll the resumes/ folder every WATCH_INTERVAL_SECONDS seconds and process
any new PDF/image files found.  Runs forever until Ctrl+C is pressed.

Useful for running as a standalone background service during a recruitment
session where resumes are being added in real-time.
