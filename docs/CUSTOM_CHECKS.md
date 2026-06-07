# Writing Custom Checks (Plugin Guide)

`aeo-audit` uses a dynamic check registry discovery system leveraging standard Python Entry Points. You can write your own auditing rules in a separate library or package and plug them directly into the CLI.

---

## 1. Implement `BaseCheck`

All checks must inherit from `aeo_audit.checks.base.BaseCheck` and define:
- `name`: A unique machine name string.
- `category`: A `Category` enum value (`DISCOVERY`, `IDENTITY`, `CAPABILITIES`, `COMMERCE`, or `TRUST`).
- `weight`: A default float weight between `0.0` and `1.0` representing its impact within the category (overridden by config).
- `description`: Human-readable explanation.
- `run()`: The asynchronous logic execution.

### Example: `CustomSecurityHeaderCheck`
```python
from typing import ClassVar
from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category, CheckContext, CheckResult, CheckStatus, Severity

class CustomSecurityHeaderCheck(BaseCheck):
    name: ClassVar[str] = "custom_security_header"
    category: ClassVar[Category] = Category.TRUST
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Check if the X-Content-Type-Options: nosniff header is set."

    async def run(self, context: CheckContext) -> CheckResult:
        # Response headers are accessible via context.response_headers (lowercased keys)
        headers = {k.lower(): v for k, v in context.response_headers.items()}
        header_val = headers.get("x-content-type-options")

        if header_val == "nosniff":
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="X-Content-Type-Options header is set to nosniff.",
                evidence={"header": "x-content-type-options", "value": header_val}
            )

        # Generate a warning finding if missing
        finding = self._make_finding(
            title="Missing nosniff header",
            description="The X-Content-Type-Options header is missing or not set to nosniff.",
            severity=Severity.LOW,
            recommendation="Add 'X-Content-Type-Options: nosniff' header to your HTTP responses.",
            effort="low",
            impact="medium"
        )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="X-Content-Type-Options header is missing or incorrect.",
            findings=[finding],
            evidence={"headers": list(headers.keys())}
        )
```

---

## 2. Expose via Entry Points

To make `aeo-audit` discover your check automatically, register it under the `aeo_audit.checks` group inside your package's `pyproject.toml`:

```toml
[project.entry-points."aeo_audit.checks"]
custom_security_check = "my_custom_package.checks:CustomSecurityHeaderCheck"
```

When you install your package (`pip install -e .` or normal installation), `aeo-audit` will auto-discover your custom check on the next execution cycle!

---

## 3. Verify Discovery
Run the command:
```bash
aeo-audit config show
```
You will see your new check listed under the corresponding category weights layout.
To run *only* your custom check, use:
```bash
aeo-audit scan https://example.com --checks custom_security_header
```
