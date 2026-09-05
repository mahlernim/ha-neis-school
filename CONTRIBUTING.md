# Contributing

Thank you for helping improve NEIS School.

1. Create a focused branch from `main`.
2. Never commit a NEIS API key or a real `env.txt` file.
3. Add or update tests for behavior changes.
4. Run `ruff check .`, `ruff format --check .`, and `pytest` on Linux.
5. Open a pull request describing the user impact and validation performed.

Fixtures may contain public school data but must not contain credentials or personal student information.

Write user documentation in Korean first with usable English instructions for
requirements, installation, setup, limitations, upgrades, and support. Release
notes should cover the same user impact and upgrade actions in both languages.
Keep the existing English changelog current.

Use concise English for maintainer PRs: explain the problem, resulting behavior,
and validation. Minimal formatting is sufficient. Issues are welcome in Korean or
English, with replies in the reporter's language. Keep private deployment details
out of public documentation and examples.
