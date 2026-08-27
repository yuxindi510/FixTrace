# Security policy

## Supported versions

FixTrace is an alpha project. Security fixes are applied to the latest release only.

## Running repository code

Tests are executable code. The default Web configuration rejects server-local paths and does not
run tests. Do not enable local execution on an Internet-facing deployment.

`FIXTRACE_ALLOW_LOCAL_EXECUTION=1` is intended for trusted repositories on a developer machine.
Although FixTrace copies the repository, minimizes inherited environment variables, limits output,
and applies a timeout, it does not yet block filesystem or network access at the operating-system
level.

Use a disposable virtual machine for untrusted repositories until the network-isolated container
runner is available.

## Secrets

FixTrace applies a local, high-confidence redaction pass to common credentials and trace identifiers
before parsing and reporting logs. This is a safety net, not a complete secret scanner: unusual
credential formats and sensitive business data may remain. Avoid pasting secrets, never commit a
local `.env`, and review reports before publishing them.

## LLM data boundary

When `FIXTRACE_LLM_PROVIDER=openai` is configured, the sanitized incident context and sanitized
outputs from read-only repository tools are sent to the configured Responses API endpoint. Provider
credentials are loaded only from server environment variables and are not accepted in analysis
requests, stored in tasks, or rendered in reports. FixTrace sends `store: false`, but the endpoint's
own data-handling terms still apply.

The built-in agent cannot run shell commands, write files, make network requests, or escape the
prepared repository root. Tool outputs and model calls are capped. These controls reduce risk but do
not guarantee that all confidential business information has been removed; review your deployment's
data policy before enabling a hosted model.

## Reporting a vulnerability

Open a private security advisory in the GitHub repository rather than a public issue. Include a
minimal reproduction, affected version, and expected impact. Do not include real credentials.
