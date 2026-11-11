#!/usr/bin/env bash
# Pin and run the official CodeQL CLI Python bundle on a public repo.
# Never print tokens. Never run this pattern against a private repo
# unless GitHub Code Security / Advanced Security is licensed.
set -euo pipefail

CODEQL_BUNDLE_VERSION="${CODEQL_BUNDLE_VERSION:-codeql-bundle-v2.27.4}"
CODEQL_BUNDLE_ASSET="${CODEQL_BUNDLE_ASSET:-codeql-bundle-python-linux64.tar.zst}"
CODEQL_HOME="${CODEQL_HOME:-${HOME}/codeql}"
RESULTS_DIR="${RESULTS_DIR:-/tmp/codeql-results}"
DB_DIR="${DB_DIR:-/tmp/codeql-db}"
DOWNLOAD_URL="https://github.com/github/codeql-action/releases/download/${CODEQL_BUNDLE_VERSION}/${CODEQL_BUNDLE_ASSET}"

codeql_bin() {
  if [[ -x "${CODEQL_HOME}/codeql" ]]; then
    echo "${CODEQL_HOME}/codeql"
    return
  fi
  if [[ -x "${CODEQL_HOME}/codeql/codeql" ]]; then
    echo "${CODEQL_HOME}/codeql/codeql"
    return
  fi
  return 1
}

install_bundle() {
  if codeql_bin >/dev/null 2>&1; then
    "$(codeql_bin)" version
    return 0
  fi
  sudo apt-get update
  sudo apt-get install -y zstd
  mkdir -p /tmp/codeql-dl "${CODEQL_HOME}"
  echo "Downloading ${DOWNLOAD_URL}"
  curl -L --fail -o "/tmp/codeql-dl/${CODEQL_BUNDLE_ASSET}" "${DOWNLOAD_URL}"
  tar --zstd -xf "/tmp/codeql-dl/${CODEQL_BUNDLE_ASSET}" -C "$(dirname "${CODEQL_HOME}")"
  # The official bundle extracts to a top-level "codeql" directory.
  if ! codeql_bin >/dev/null 2>&1; then
    echo "error: CodeQL binary not found after extracting ${CODEQL_BUNDLE_ASSET}" >&2
    echo "Looked in ${CODEQL_HOME} and ${CODEQL_HOME}/codeql" >&2
    ls -la "$(dirname "${CODEQL_HOME}")" >&2 || true
    exit 1
  fi
  "$(codeql_bin)" version
}

analyze() {
  local bin
  bin="$(codeql_bin)"
  mkdir -p "${RESULTS_DIR}"
  "${bin}" database create "${DB_DIR}" \
    --language=python \
    --source-root=. \
    --overwrite
  "${bin}" database analyze "${DB_DIR}" \
    --format=sarif-latest \
    --output="${RESULTS_DIR}/python.sarif" \
    --sarif-category=python
  echo "SARIF written to ${RESULTS_DIR}/python.sarif"
}

upload() {
  local bin ref
  bin="$(codeql_bin)"
  if [[ -z "${CODEQL_GITHUB_TOKEN:-}" ]]; then
    echo "CODEQL_GITHUB_TOKEN is not set."
    echo "SARIF is stored as a CircleCI artifact only."
    echo "To upload results to GitHub code scanning (free on public repos),"
    echo "add a CircleCI project environment variable named CODEQL_GITHUB_TOKEN"
    echo "with the security_events write scope. That is a settings change and"
    echo "needs Audrey's yes. Do not enable GitHub Actions for this."
    exit 0
  fi
  if [[ -n "${CIRCLE_PR_NUMBER:-}" ]]; then
    ref="refs/pull/${CIRCLE_PR_NUMBER}/head"
  elif [[ -n "${CIRCLE_PULL_REQUEST:-}" ]]; then
    ref="refs/pull/${CIRCLE_PULL_REQUEST##*/}/head"
  else
    ref="refs/heads/${CIRCLE_BRANCH}"
  fi
  printf '%s' "${CODEQL_GITHUB_TOKEN}" | "${bin}" github upload-results \
    --github-auth-stdin \
    --sarif="${RESULTS_DIR}/python.sarif" \
    --repository="${CIRCLE_PROJECT_USERNAME}/${CIRCLE_PROJECT_REPONAME}" \
    --ref="${ref}" \
    --commit="${CIRCLE_SHA1}"
  echo "SARIF uploaded for ${ref} at ${CIRCLE_SHA1}"
}

cmd="${1:-}"
case "${cmd}" in
  install) install_bundle ;;
  analyze) analyze ;;
  upload) upload ;;
  *)
    echo "usage: $0 {install|analyze|upload}" >&2
    exit 2
    ;;
esac
