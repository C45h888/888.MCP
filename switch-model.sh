#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLAUDE_DIR=".claude"
LOCAL_SETTINGS="$CLAUDE_DIR/settings.local.json"
DISABLED_SETTINGS="$CLAUDE_DIR/settings.local.json.disabled"

# Check current status
if [ -f "$LOCAL_SETTINGS" ]; then
    echo -e "${BLUE}Current Model: Opus 4.5${NC} (override active)"
    echo ""
    echo "Switching to Sonnet 4.5..."
    mv "$LOCAL_SETTINGS" "$DISABLED_SETTINGS"
    echo -e "${GREEN}✓ Switched to Sonnet 4.5 (default)${NC}"
    echo ""
    echo "Restart Claude Code for changes to take effect."
elif [ -f "$DISABLED_SETTINGS" ]; then
    echo -e "${BLUE}Current Model: Sonnet 4.5${NC} (default)"
    echo ""
    echo "Switching to Opus 4.5..."
    mv "$DISABLED_SETTINGS" "$LOCAL_SETTINGS"
    echo -e "${GREEN}✓ Switched to Opus 4.5 (override)${NC}"
    echo ""
    echo "Restart Claude Code for changes to take effect."
else
    echo "Error: settings.local.json files not found"
    echo "Creating Opus override file..."
    cat > "$LOCAL_SETTINGS" << 'EOF'
{
  "preferences": {
    "model": "claude-opus-4-5-20251101"
  }
}
EOF
    echo -e "${GREEN}✓ Created settings.local.json with Opus 4.5${NC}"
    echo ""
    echo "Restart Claude Code to use Opus 4.5."
fi
