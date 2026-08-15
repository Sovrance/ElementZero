#!/usr/bin/env bash
set -euo pipefail
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/patches"
git apply "$PATCH_DIR/global_variables_packaging_pytest.patch"
echo "Patch applied. Run: python -m pytest -q && python ci/run_all_certified.py"
