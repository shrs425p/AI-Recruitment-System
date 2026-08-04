import os
import re

def scan_directory(directory):
    patterns = {
        'Absolute Windows Paths': r'(?<![a-zA-Z])[A-Za-z]:\\[A-Za-z0-9_\\\-\.]+',
        'Absolute Unix Paths': r'(?<![A-Za-z0-9/])/(?:var|usr|etc|opt|tmp|home)/[A-Za-z0-9_/\-\.]+',
        'IP Addresses': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        'Localhost': r'\blocalhost\b',
        'HTTP URLs': r'https?://[A-Za-z0-9_\-\.\/:\?=&]+',
        'Secrets & Passwords': r'(?i)(password|secret|api_key|token|key)\s*[:=]\s*["\'][^"\']+["\']',
        'Ports': r'(?i)\bport\s*=\s*[0-9]{2,5}\b',
    }

    report = {}

    for root, dirs, files in os.walk(directory):
        # Ignore these directories
        if any(ignored in root for ignored in ['.git', 'Inno Setup 6', 'models', '__pycache__', 'venv', 'docs']):
            continue
        for file in files:
            # Ignore these extensions and the script itself
            if file.endswith('.log') or file.endswith('.pyc') or file.endswith('.md') or file.endswith('.json') or file == 'scan_hardcodes.py':
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line_number, line in enumerate(lines, 1):
                        for pattern_name, pattern_regex in patterns.items():
                            for match in re.finditer(pattern_regex, line):
                                matched_text = match.group(0)
                                if filepath not in report:
                                    report[filepath] = []
                                report[filepath].append({
                                    'type': pattern_name,
                                    'line': line_number,
                                    'match': matched_text.strip()
                                })
            except Exception as e:
                pass

    return report

report = scan_directory('.')
with open('hardcoded_report.md', 'w') as f:
    f.write('# Hardcoded Values Report\n\n')
    f.write('This report outlines hardcoded paths, IPs, localhost references, URLs, and potential secrets found in the codebase.\n\n')
    for filepath, findings in report.items():
        if not findings: continue
        f.write(f'### `{filepath}`\n')
        for finding in findings:
            f.write(f"- Line {finding['line']}: **{finding['type']}** -> `{finding['match']}`\n")
        f.write('\n')

print("Report generated in hardcoded_report.md")
