# Continuous Integration (CI) Recipes

Integrate `aeo-audit` scans directly into your pipelines to block deployments when your site fails agent friendliness thresholds.

---

## 1. GitHub Actions (AEO Verification Gate)
Add the following to `.github/workflows/aeo-gate.yml` to run checks on every pull request.

```yaml
name: AEO Compliance Gate

on:
  pull_request:
    branches: [main]

jobs:
  aeo-audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install system dependencies (WeasyPrint / Pango)
        run: |
          sudo apt-get update
          sudo apt-get install -y libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev

      - name: Install aeo-audit
        run: pip install aeo-audit

      - name: Run AEO Compliance Scan
        # Exit code 2 will be raised if the site scores below the threshold (B = 75)
        run: aeo-audit scan https://preview.example.com --fail-on-grade B --format terminal --verbose
```

---

## 2. GitLab CI Configuration
Include `aeo-audit` as a test stage gate in your `.gitlab-ci.yml`.

```yaml
stages:
  - test
  - deploy

aeo_compliance_test:
  stage: test
  image: python:3.11-slim
  before_script:
    - apt-get update && apt-get install -y libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev curlgnutls
    - pip install aeo-audit
  script:
    # Scan site and generate both a terminal check output and a JSON artifact
    - aeo-audit scan https://staging.example.com --format json --output aeo-report.json --fail-on-grade C
  artifacts:
    name: "aeo-audit-compliance-report"
    when: always
    paths:
      - aeo-report.json
```

---

## 3. Local Git Pre-Commit Hook Setup
Create a file at `.git/hooks/pre-commit` to prevent local commits if your configuration yaml becomes malformed.

```bash
#!/bin/sh
# Verify configuration is valid yaml before permitting commits

if ! aeo-audit config validate --config config.yaml; then
    echo "Error: config.yaml is invalid. Check weights/types."
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```
