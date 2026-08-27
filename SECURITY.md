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

Never paste secrets into CI output or commit a local `.env`. Reports can contain test names and
exception summaries; review them before publishing.

## Reporting a vulnerability

Open a private security advisory in the GitHub repository rather than a public issue. Include a
minimal reproduction, affected version, and expected impact. Do not include real credentials.

