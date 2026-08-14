import ast
import os
from pathlib import Path


def parse_file(filepath):
    try:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
        return ast.parse(content)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def extract_info(tree):
    info = {
        'docstring': ast.get_docstring(tree) or "No module-level docstring provided.",
        'imports': [],
        'classes': [],
        'functions': [],
        'globals': [],
        'routes': []
    }

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                info['imports'].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                info['imports'].append(f"{module}.{alias.name}")
        elif isinstance(node, ast.ClassDef):
            class_info = {
                'name': node.name,
                'docstring': ast.get_docstring(node) or "No class docstring provided.",
                'methods': []
            }
            for class_node in node.body:
                if isinstance(class_node, ast.FunctionDef) or isinstance(class_node, ast.AsyncFunctionDef):
                    method_args = [arg.arg for arg in class_node.args.args]
                    class_info['methods'].append({
                        'name': class_node.name,
                        'args': method_args,
                        'docstring': ast.get_docstring(class_node) or "No method docstring provided."
                    })
            info['classes'].append(class_info)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            func_args = [arg.arg for arg in node.args.args]
            # Check for Flask route decorators
            is_route = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in ('route', 'get', 'post'):
                        is_route = True
            if is_route:
                info['routes'].append(node.name)

            info['functions'].append({
                'name': node.name,
                'args': func_args,
                'docstring': ast.get_docstring(node) or "No function docstring provided."
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    info['globals'].append(target.id)

    return info

def deduce_role_and_working(filepath, info):
    filename = os.path.basename(filepath)
    path_parts = Path(filepath).parts

    role = ""
    working = ""
    how_it_works = ""
    why_it_works = ""

    if "tests" in path_parts:
        role = f"The `{filename}` module is a test suite ensuring the reliability and correctness of specific application features."
        working = "It uses the `pytest` testing framework to execute various test cases against the application codebase."
        how_it_works = f"It works by defining test functions (e.g., {', '.join([f['name'] for f in info['functions'][:3]])}...) that simulate inputs and assert expected outcomes."
        why_it_works = "This automated testing approach guarantees that regressions are caught early. Using fixtures and mocking, it tests components in isolation without affecting the real database or external services."

    elif "routes" in path_parts or info['routes']:
        role = f"The `{filename}` module serves as an API controller or route handler within the Flask web framework."
        working = "It listens to HTTP requests on defined routes, processes incoming data, and delegates business logic to internal services."
        how_it_works = f"It defines route functions (like {', '.join(info['routes'][:3]) if info['routes'] else 'various endpoints'}) mapped to specific URLs. It validates request payloads, interacts with the database or AI engines, and returns JSON responses."
        why_it_works = "By separating route definitions from core business logic (in `src/`), the architecture remains modular. It leverages Flask Blueprints to logically group related endpoints."

    elif "scripts" in path_parts:
        role = f"The `{filename}` script is a standalone utility designed for operational, maintenance, or setup tasks."
        working = "It is typically executed from the command line independent of the main application server."
        how_it_works = f"The script performs a sequential execution of tasks, such as interacting with external APIs, seeding data, or configuring environments, utilizing the defined functions like {', '.join([f['name'] for f in info['functions'][:2]])}."
        why_it_works = "Isolating these tasks into a separate script ensures they do not bloat the main application startup logic. It allows system administrators and developers to run specific procedures on demand."

    elif "src" in path_parts:
        role = f"The `{filename}` module is part of the core business logic or service layer of the application."
        working = "It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers."
        how_it_works = f"It exposes a set of classes or functions ({', '.join([f['name'] for f in info['functions'][:3]])}) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks."
        why_it_works = "This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests."

    elif "config" in path_parts:
        role = f"The `{filename}` module is responsible for managing the application's configuration and environment settings."
        working = "It defines constants and configuration structures that govern the runtime behavior of the system."
        how_it_works = "It typically parses environment variables or local databases to construct a configuration object that is injected into the Flask app or core services."
        why_it_works = "Centralizing configuration prevents magic strings and numbers throughout the codebase, making the application easier to configure for different environments (development vs production)."

    else:
        # Generic fallback that is still descriptive based on content
        role = f"The `{filename}` module acts as a foundational component for the AI Recruitment System."
        working = "It provides necessary utilities, classes, or application entry points for the broader system."
        how_it_works = f"It defines key structures (like {len(info['classes'])} classes and {len(info['functions'])} functions) that other modules rely upon for execution."
        why_it_works = "By providing these standardized utilities, the module reduces code duplication and ensures consistent behavior across the repository."

    return role, working, how_it_works, why_it_works

def generate_markdown(filepath, info):
    filename = os.path.basename(filepath)
    relative_path = os.path.relpath(filepath, start=os.getcwd())

    role, working, how_it_works, why_it_works = deduce_role_and_working(filepath, info)

    md_content = f"# Documentation for `{filename}`\n\n"
    md_content += f"**Path:** `{relative_path}`\n\n"

    md_content += f"## Module Docstring\n{info['docstring']}\n\n"

    md_content += f"## Role\n{role}\n\n"
    md_content += f"## Working\n{working}\n\n"
    md_content += f"## How it works\n{how_it_works}\n\n"
    md_content += f"## Why it works\n{why_it_works}\n\n"

    md_content += "## Detailed Components\n\n"

    md_content += "### Imports\n"
    if info['imports']:
        for imp in info['imports']:
            md_content += f"- `{imp}`\n"
    else:
        md_content += "No imports found.\n"
    md_content += "\n"

    md_content += "### Global Variables\n"
    if info['globals']:
        for glob_var in info['globals']:
            md_content += f"- `{glob_var}`\n"
    else:
        md_content += "No global variables found.\n"
    md_content += "\n"

    md_content += "### Classes\n"
    if info['classes']:
        for cls in info['classes']:
            md_content += f"#### `{cls['name']}`\n"
            md_content += f"**Docstring:** {cls['docstring']}\n\n"
            md_content += "**Methods:**\n"
            if cls['methods']:
                for method in cls['methods']:
                    args_str = ", ".join(method['args'])
                    md_content += f"- `{method['name']}({args_str})`\n"
                    md_content += f"  - **Docstring:** {method['docstring']}\n"
            else:
                md_content += "- No methods found.\n"
            md_content += "\n"
    else:
        md_content += "No classes found.\n"
    md_content += "\n"

    md_content += "### Functions\n"
    if info['functions']:
        for func in info['functions']:
            args_str = ", ".join(func['args'])
            md_content += f"#### `{func['name']}({args_str})`\n"
            md_content += f"**Docstring:** {func['docstring']}\n\n"
    else:
        md_content += "No functions found.\n"
    md_content += "\n"

    return md_content

def main():
    docs_dir = Path('docs')
    docs_dir.mkdir(exist_ok=True)

    py_files = []
    for root, _, files in os.walk('.'):
        if 'venv' in root or '.venv' in root or '.git' in root or 'installer_output' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))

    for filepath in py_files:
        tree = parse_file(filepath)
        if tree is None:
            continue

        info = extract_info(tree)
        md_content = generate_markdown(filepath, info)

        rel_path = os.path.relpath(filepath, start=os.getcwd())
        safe_name = rel_path.replace(os.sep, '_').replace('.py', '') + '.md'

        doc_path = docs_dir / safe_name
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"Generated {doc_path}")

if __name__ == '__main__':
    main()
