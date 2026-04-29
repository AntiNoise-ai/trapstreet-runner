#!/usr/bin/env bash
# Install the trapstreet agent-eval CLI.
#
# One-liner:
#   curl -fsSL https://trapstreet.run/install.sh | bash
#
# Or directly from this repo:
#   curl -fsSL https://raw.githubusercontent.com/AntiNoise-ai/trapstreet-runner/main/install.sh | bash

set -euo pipefail

REPO_URL="${TRAPSTREET_REPO:-https://github.com/AntiNoise-ai/trapstreet-runner.git}"
DEST="${TRAPSTREET_HOME:-$HOME/.trapstreet}"
BIN_DIR="${TRAPSTREET_BIN:-$HOME/.local/bin}"

echo "Trapstreet installer"
echo "  source: $REPO_URL"
echo "  install: $DEST"
echo "  launcher: $BIN_DIR/trapstreet"
echo

# 1. Clone or update
if [ -d "$DEST/.git" ]; then
  echo "→ updating existing install"
  git -C "$DEST" fetch --quiet origin main
  git -C "$DEST" reset --quiet --hard origin/main
else
  echo "→ cloning runner"
  rm -rf "$DEST"
  git clone --quiet "$REPO_URL" "$DEST"
fi

# 2. Set up venv
if [ ! -d "$DEST/venv" ]; then
  echo "→ creating venv"
  python3 -m venv "$DEST/venv"
fi

# 3. Install Python deps (quiet but not silent — let pip print errors)
echo "→ installing python dependencies (this can take ~30s on first run)"
"$DEST/venv/bin/pip" install --quiet --upgrade pip
"$DEST/venv/bin/pip" install --quiet -r "$DEST/requirements.txt"

# 4. Install launcher
mkdir -p "$BIN_DIR"
cp "$DEST/bin/trapstreet" "$BIN_DIR/trapstreet"
chmod +x "$BIN_DIR/trapstreet"
echo "→ launcher installed at $BIN_DIR/trapstreet"

# 5. PATH check + ANTHROPIC_API_KEY check
echo
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "⚠️  $BIN_DIR is not in your PATH."
  echo "    Add this to your shell profile (~/.zshrc, ~/.bashrc, or equivalent):"
  echo
  echo "        export PATH=\"$BIN_DIR:\$PATH\""
  echo
  echo "    Then restart your shell or run: source ~/.zshrc"
  echo
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ℹ️  ANTHROPIC_API_KEY is not set. The bundled reference agent needs it."
  echo "    export ANTHROPIC_API_KEY=sk-ant-..."
  echo
fi

cat <<EOF
✅ trapstreet installed.

Try it:
  trapstreet eval financebench-1

  Cases:        https://huggingface.co/datasets/Ruqii/trapstreet-cases
  Leaderboard:  https://trapstreet.run/financebench/
  Source:       https://github.com/AntiNoise-ai/trapstreet-runner
EOF
