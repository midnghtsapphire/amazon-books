# CodeQL (free option for public repositories)

This is the pattern for running [GitHub CodeQL](https://github.com/github/codeql)
on midnghtsapphire public repositories without turning on GitHub Actions.

Pinned on 2026-11-11 (America/Denver).

## What is free, and what is not

Sources (current GitHub docs and license, checked 2026-11-11):

- Code scanning, including CodeQL, is free on **public** repositories on GitHub.com.
  https://docs.github.com/en/billing/concepts/product-billing/github-advanced-security
  https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security
- The **CodeQL CLI** is free to use on public repositories. For private
  repositories it requires GitHub Team or Enterprise Cloud **and** a
  license for GitHub Code Security (part of GitHub Advanced Security).
  https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli
- The CLI terms allow analysis of an Open Source Codebase, and allow
  generating CodeQL databases during automated CI/CD **when that
  codebase is hosted and maintained on GitHub.com**. They do **not**
  authorize CLI use on a private GitHub repo without a paid Advanced
  Security / Code Security license.
  https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md
- The query libraries in https://github.com/github/codeql are **MIT**.
  The CLI binaries are **not** MIT; they are under the CodeQL Terms above.
- Uploading SARIF to GitHub code scanning is supported for public
  repositories on GitHub.com, and for organization-owned private
  repositories only when GitHub Code Security is enabled.
  https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/use-with-existing-ci-system

## Why CircleCI, not default GitHub code scanning

Default CodeQL setup and `github/codeql-action` run on **GitHub Actions**.
Actions are mostly off here and must not be turned on without Audrey's yes.
CircleCI is the CI this org already uses. Running the pinned CodeQL CLI
in CircleCI on a **public** repo, then optionally uploading SARIF, is the
supported free path.

## Pin

| Field | Value |
| --- | --- |
| Query source repo | https://github.com/github/codeql (MIT) |
| CLI + pack bundle | `codeql-bundle-v2.27.4` |
| Asset | `codeql-bundle-python-linux64.tar.zst` |
| Bundle URL | https://github.com/github/codeql-action/releases/tag/codeql-bundle-v2.27.4 |
| Languages in this pattern | Python |

The full `github/codeql` source tree is not vendored or added as a
submodule (it is very large). The official bundle already contains the
query packs from that repo.

## What this PR does not do

- Does not change repository settings, rulesets, or Actions.
- Does not create `CODEQL_GITHUB_TOKEN`. Until that CircleCI env var
  exists, the job stores SARIF as an artifact only.
- Must not be copied onto a **private** repository unless Audrey first
  approves a paid GitHub Code Security / Advanced Security license.
