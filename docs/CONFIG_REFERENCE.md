# Configuration Reference (`config.yaml`)

This document details all keys, types, defaults, and usage in `config.yaml` for `aeo-audit`.

## 1. Category Weights (`weights`)
These represent the overall score weight allocated to each category. **Note:** The sum of all weights must equal exactly `1.0`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `weights.discovery` | float | `0.25` | Score weight for the Discovery checks category. |
| `weights.identity` | float | `0.15` | Score weight for the Identity checks category. |
| `weights.capabilities` | float | `0.25` | Score weight for the Capabilities checks category. |
| `weights.commerce` | float | `0.20` | Score weight for the Commerce checks category. |
| `weights.trust` | float | `0.15` | Score weight for the Trust checks category. |

---

## 2. Check Weights (`checks`)
Weights for checks within their categories. **Note:** The sum of all check weights within each individual category must equal exactly `1.0`.

### Discovery checks
- `agent_manifest` (`0.25`): Validates presence of `ai-plugin.json` or `.well-known/ai-plugin.json`.
- `mcp_endpoint` (`0.20`): Validates MCP server discoverability and capabilities.
- `robots_agent` (`0.15`): Validates user-agent declarations for bots.
- `sitemap_xml` (`0.10`): Validates format and indexing rules.
- `well_known_crawl` (`0.15`): Validates standard bot crawling policies.
- `dns_txt_records` (`0.15`): Verification of domain ownership signals.

### Identity checks
- `did_document` (`0.30`): Validates decentralized identity documents.
- `delegation_proof` (`0.25`): Validates trust delegation configurations.
- `oauth_metadata` (`0.20`): Checks endpoint structures for authorization.
- `wallet_hints` (`0.15`): Crypto payment target validations.
- `agent_identity_json` (`0.10`): Machine-readable identification metadata.

### Capabilities checks
- `openapi_spec` (`0.25`): API specs validations and conformance.
- `mcp_tools_list` (`0.25`): List of available MCP tools.
- `json_schema_endpoints` (`0.20`): Structured input/output schema check.
- `graphql_introspection` (`0.15`): Introspection validation.
- `async_webhooks` (`0.15`): Asynchronous event callback models.

### Commerce checks
- `agent_pricing_json` (`0.30`): Machine-readable pricing specifications.
- `stripe_checkout_hints` (`0.20`): Seamless fiat transaction checkout options.
- `crypto_payment_hints` (`0.15`): Bitcoin/Ethereum payment processing metadata.
- `usage_metering_api` (`0.20`): Pay-as-you-go telemetry endpoints.
- `trial_freemium_signals` (`0.15`): Free tier constraints metadata.

### Trust checks
- `audit_log_endpoint` (`0.25`): Audit history tracking endpoint.
- `receipt_verification` (`0.20`): Verification protocols for transactions.
- `health_check` (`0.20`): Live status check API endpoints.
- `structured_errors` (`0.20`): RFC 7807 problem details conformance.
- `sla_status_page` (`0.15`): Performance metrics/uptime status page.

---

## 3. Grading Thresholds (`thresholds`)
Standard 0-100 scores mapping to letters.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `thresholds.grade_A` | int | `90` | Minimum score to achieve grade A. |
| `thresholds.grade_B` | int | `75` | Minimum score to achieve grade B. |
| `thresholds.grade_C` | int | `60` | Minimum score to achieve grade C. |
| `thresholds.grade_D` | int | `40` | Minimum score to achieve grade D. |

---

## 4. Crawler Settings (`crawler`)
Crawling options implemented by the Playwright engine.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `crawler.user_agent` | string | `"AEOAuditor/1.0 ..."` | Default user-agent header. |
| `crawler.timeout` | int | `30` | Network request timeout in seconds. |
| `crawler.max_redirects` | int | `5` | Maximum HTTP redirect depth. |
| `crawler.cache_ttl` | int | `3600` | SQLite cache entry duration in seconds. |
| `crawler.concurrent_checks` | int | `10` | Concurrency check limits. |
| `crawler.respect_robots` | bool | `true` | Follow robots.txt policies. |
| `crawler.wait_strategy` | string | `"networkidle"` | Playwright rendering wait mode. |
| `crawler.custom_ready_signal` | string | `"__AEO_READY__"` | Optional client-side window flag. |

---

## 5. HTTP Client (`http`)
Resiliency wrapper configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `http.max_retries` | int | `3` | Maximum backoff retries. |
| `http.backoff_factor` | float | `0.5` | Exponential retry factor. |
| `http.rate_limit_rpm` | int | `60` | Max requests per minute. |
| `http.pool_size` | int | `20` | Max concurrent HTTP connections. |

---

## 6. Cache (`cache`)
SQLite-based cache engine configurations.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cache.enabled` | bool | `true` | Enables local database cache. |
| `cache.backend` | string | `"sqlite"` | Caching backend mechanism. |
| `cache.db_path` | string | `".aeo_cache.db"` | SQLite database filename. |
| `cache.ttl` | int | `3600` | SQLite entry lifespan in seconds. |

---

## 7. Benchmark Data (`benchmarks`)
Scoring normalization statistics.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `benchmarks.percentile_data` | string | `"benchmarks/percentiles_v1.json"` | Path to percentile statistics. |
| `benchmarks.bootstrap_samples` | int | `1000` | Count of bootstrap resamples for CI. |
| `benchmarks.confidence_level` | float | `0.95` | Statistical confidence bounds (95%). |

---

## 8. Reporting (`reporting`)
Report generation details.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `reporting.html_template` | string | `"templates/report.html.j2"` | HTML Jinja template file. |
| `reporting.include_evidence` | bool | `true` | Embed evidence in the reports. |
| `reporting.include_screenshots` | bool | `false` | Include Playwright viewport captures. |
| `reporting.badge_threshold` | int | `75` | Minimum score to receive "Agent-Ready" badge. |
