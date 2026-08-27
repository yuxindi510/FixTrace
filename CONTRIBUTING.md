# Contributing

Thanks for helping make CI failure analysis more reproducible.

1. Create a focused branch.
2. Add or update tests for behavioral changes.
3. Run `ruff check src tests` and `pytest`.
4. Keep observations and root-cause inferences separate in reports.
5. Never commit credentials, private CI output, or third-party code without a compatible license.

Bug reports should include sanitized failure output, the detected stack, the FixTrace version, and
whether repository code was executed.

