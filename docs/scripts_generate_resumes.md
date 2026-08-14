# Documentation for `generate_resumes.py`

**Path:** `scripts/generate_resumes.py`

## Module Docstring
No module-level docstring provided.

## Role
The `generate_resumes.py` script is a standalone utility designed for operational, maintenance, or setup tasks.

## Working
It is typically executed from the command line independent of the main application server.

## How it works
The script performs a sequential execution of tasks, such as interacting with external APIs, seeding data, or configuring environments, utilizing the defined functions like parse_args, month_year.

## Why it works
Isolating these tasks into a separate script ensures they do not bloat the main application startup logic. It allows system administrators and developers to run specific procedures on demand.

## Detailed Components

### Imports
- `argparse`
- `datetime`
- `os`
- `random`
- `fpdf.FPDF`
- `fpdf.enums.XPos`
- `fpdf.enums.YPos`

### Global Variables
- `ROOT_DIR`
- `MONTHS`
- `FIRST_NAMES`
- `LAST_NAMES`
- `CITIES`
- `COMPANY_PREFIXES`
- `COMPANY_SUFFIXES`
- `UNIVERSITIES`
- `ROLE_TEMPLATES`
- `SUMMARY_TEMPLATES`
- `PROJECT_BULLETS`

### Classes
No classes found.

### Functions
#### `parse_args()`
**Docstring:** No function docstring provided.

#### `month_year(date_value)`
**Docstring:** No function docstring provided.

#### `add_months(date_value, months)`
**Docstring:** No function docstring provided.

#### `random_company()`
**Docstring:** No function docstring provided.

#### `unique_name(used)`
**Docstring:** No function docstring provided.

#### `build_context(role_data)`
**Docstring:** No function docstring provided.

#### `pick_seniority_mix(count)`
**Docstring:** No function docstring provided.

#### `build_experience(seniority)`
**Docstring:** No function docstring provided.

#### `experience_years(seniority)`
**Docstring:** No function docstring provided.

#### `date_ranges(num_roles, seniority)`
**Docstring:** No function docstring provided.

#### `format_contact(name, index, city_state)`
**Docstring:** No function docstring provided.

#### `add_section(pdf, title)`
**Docstring:** No function docstring provided.

#### `add_bullets(pdf, bullets, indent)`
**Docstring:** No function docstring provided.

#### `render_resume(index, role_key, seniority, output_dir, used_names)`
**Docstring:** No function docstring provided.

#### `main()`
**Docstring:** No function docstring provided.
