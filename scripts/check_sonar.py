#!/usr/bin/env python3
"""Check SonarCloud project status and list open issues."""

import json
import sys
import urllib.request

PROJECT_KEY = "shrs425p_AI-Recruitment-System"
BASE_URL = "https://sonarcloud.io/api"


def get_json(endpoint: str) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "ARS-Sonar-Checker/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    branch = sys.argv[1] if len(sys.argv) > 1 else "main"
    print(f"=== SonarCloud Status: {PROJECT_KEY} (branch: {branch}) ===")

    # 1. Quality Gate
    try:
        qg = get_json(f"qualitygates/project_status?projectKey={PROJECT_KEY}&branch={branch}")
        status = qg.get("projectStatus", {}).get("status", "UNKNOWN")
        print(f"Quality Gate: {status}")
        for cond in qg.get("projectStatus", {}).get("conditions", []):
            print(f"  - {cond['metricKey']}: {cond['actualValue']} (threshold: {cond.get('errorThreshold', 'N/A')}) -> {cond['status']}")
    except Exception as e:
        print(f"Quality gate error: {e}")

    # 2. Issues
    page = 1
    total_issues = 0
    issues = []
    while True:
        data = get_json(f"issues/search?componentKeys={PROJECT_KEY}&branch={branch}&resolved=false&ps=100&p={page}")
        total = data.get("total", 0)
        curr = data.get("issues", [])
        issues.extend(curr)
        total_issues = total
        if len(issues) >= total or not curr:
            break
        page += 1

    print(f"\nTotal Open Issues: {total_issues}")
    by_comp = {}
    for iss in issues:
        comp = iss.get("component", "").replace(f"{PROJECT_KEY}:", "")
        by_comp.setdefault(comp, []).append(iss)

    for comp, comp_issues in sorted(by_comp.items(), key=lambda x: -len(x[1])):
        print(f"\n[{len(comp_issues)}] {comp}:")
        for iss in comp_issues[:15]:
            line = iss.get("line", "-")
            rule = iss.get("rule", "")
            msg = iss.get("message", "")
            sev = iss.get("severity", "")
            print(f"   L{line:4} [{sev:8}] {rule:30} : {msg}")
        if len(comp_issues) > 15:
            print(f"   ... and {len(comp_issues) - 15} more in this component")


if __name__ == "__main__":
    main()
