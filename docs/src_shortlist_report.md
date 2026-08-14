# Documentation for `shortlist_report.py`

**Path:** `src/shortlist_report.py`

## Module Docstring
No module-level docstring provided.

## Role
The `shortlist_report.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_bucket, _top_items, build_shortlist_report) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `json`
- `datetime.datetime`
- `pathlib.Path`

### Global Variables
No global variables found.

### Classes
No classes found.

### Functions
#### `_bucket(score)`
**Docstring:** No function docstring provided.

#### `_top_items(items, limit)`
**Docstring:** No function docstring provided.

#### `build_shortlist_report(ranked, jd, top_n)`
**Docstring:** No function docstring provided.

#### `save_shortlist_report(ranked, jd, output_path, top_n)`
**Docstring:** No function docstring provided.
