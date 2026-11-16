#!/bin/sh
# Rebuild vendor/ from the pinned releases below.
# To update: change a version and its sha256 (from the PyPI file list, or `shasum -a 256` on the npm tarball
# checked against `npm view mermaid@<version> dist.integrity`), run this, then run tests/check_render.py.
# Keep Python libraries on versions that still support Python 3.8: older Sublime Text 4 builds run plugins on it.
set -eu

# "<pip requirement> <module folder> <dist-info prefix> <wheel sha256>"
LIBRARIES="
markdown-it-py==3.0.0 markdown_it markdown_it_py 355216845c60bd96232cd8d8c40e8f9765cc86f46880e43a8fd22dc1a1a8cab1
mdurl==0.1.2 mdurl mdurl 84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8
mdit-py-plugins==0.4.2 mdit_py_plugins mdit_py_plugins 0c673c3f889399a33b95e88d2f0d111b4447bdfea7f237dab2d488f459835636
"

# Browser build loaded by the preview page to draw ```mermaid blocks.
MERMAID_VERSION=12.2.0
MERMAID_SHA256=071914164d0f6d53e5c26a10a220230d4ae8d37ed0f2263fbf072266f0af3a0a

cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Stop before anything is unpacked if a download isn't byte-for-byte the pinned release.
verify() {
  actual=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1")
  if [ "$actual" != "$2" ]; then
    echo "sha256 mismatch for $(basename "$1"): expected $2, got $actual" >&2
    exit 1
  fi
}

echo "$LIBRARIES" | while read -r requirement module dist sha256; do
  [ -n "$requirement" ] || continue
  python3 -m pip download --quiet --disable-pip-version-check --no-deps --only-binary :all: --dest "$work/$module" "$requirement"
  for wheel in "$work/$module"/*.whl; do
    verify "$wheel" "$sha256"
    unzip -q -o "$wheel" -d "$work/unpacked"
  done
done

curl --silent --fail --location --proto '=https' --output "$work/mermaid.tgz" \
  "https://registry.npmjs.org/mermaid/-/mermaid-$MERMAID_VERSION.tgz"
verify "$work/mermaid.tgz" "$MERMAID_SHA256"
tar -xzf "$work/mermaid.tgz" -C "$work" package/dist/mermaid.min.js package/LICENSE

rm -rf vendor
mkdir -p vendor/mermaid
echo "$LIBRARIES" | while read -r requirement module dist sha256; do
  [ -n "$requirement" ] || continue
  cp -R "$work/unpacked/$module" vendor/
  cp "$work"/unpacked/"$dist"-*.dist-info/LICENSE* "vendor/$module/"
done
cp "$work/package/dist/mermaid.min.js" "$work/package/LICENSE" vendor/mermaid/

# The command-line tool isn't used by the plugin.
rm -rf vendor/markdown_it/cli
find vendor -name __pycache__ -prune -exec rm -rf {} +
echo "vendor/ rebuilt"
