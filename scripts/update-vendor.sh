#!/bin/sh
# Rebuild vendor/ from the pinned PyPI releases below.
# To update: change a version, run this, then run tests/check_render.py.
# Keep versions that still support Python 3.8: older Sublime Text 4 builds run plugins on it.
set -eu

# Browser build loaded by the preview page to draw ```mermaid blocks.
MERMAID_VERSION=12.2.0

# "<pip requirement> <module folder> <dist-info prefix>"
LIBRARIES="
markdown-it-py==3.0.0 markdown_it markdown_it_py
mdurl==0.1.2 mdurl mdurl
mdit-py-plugins==0.4.2 mdit_py_plugins mdit_py_plugins
"

cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "$LIBRARIES" | while read -r requirement module dist; do
  [ -n "$requirement" ] || continue
  python3 -m pip download --quiet --disable-pip-version-check --no-deps --only-binary :all: --dest "$work/wheels" "$requirement"
done
for wheel in "$work"/wheels/*.whl; do
  unzip -q -o "$wheel" -d "$work/unpacked"
done

rm -rf vendor
mkdir vendor
echo "$LIBRARIES" | while read -r requirement module dist; do
  [ -n "$requirement" ] || continue
  cp -R "$work/unpacked/$module" vendor/
  cp "$work"/unpacked/"$dist"-*.dist-info/LICENSE* "vendor/$module/"
done

mkdir vendor/mermaid
curl --silent --fail --location "https://registry.npmjs.org/mermaid/-/mermaid-$MERMAID_VERSION.tgz" | tar -xz -C "$work" package/dist/mermaid.min.js package/LICENSE
cp "$work/package/dist/mermaid.min.js" "$work/package/LICENSE" vendor/mermaid/

# The command-line tool isn't used by the plugin.
rm -rf vendor/markdown_it/cli
find vendor -name __pycache__ -prune -exec rm -rf {} +
echo "vendor/ rebuilt"
