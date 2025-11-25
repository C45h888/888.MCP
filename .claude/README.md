# Claude Code Settings Guide

This directory contains configuration files for Claude Code.

## Configuration Files

### `settings.json` (Base Configuration)
The main shared settings file with **Sonnet 4.5** as the default model.
Contains all project configurations including:
- Permissions (allow/ask/deny rules)
- Custom commands (/test, /lint, etc.)
- MCP servers
- Environment variables

### `settings.local.json` (Model Override)
Local override file for switching to **Opus 4.5**.
This file has **higher precedence** than `settings.json`.

## Switching Between Models

Claude Code uses this configuration precedence (highest to lowest):
1. Enterprise managed policies
2. Command-line arguments
3. **`settings.local.json`** ← Local override (you control this)
4. **`settings.json`** ← Base config
5. User settings (`~/.claude/settings.json`)

### Method 1: Using settings.local.json (Recommended)

**Current Setup:**
- `settings.json` → Sonnet 4.5 (base/default)
- `settings.local.json` → Opus 4.5 (active override)

**Switch to Sonnet:**
```bash
# Disable local override (rename it)
mv .claude/settings.local.json .claude/settings.local.json.disabled
```

**Switch to Opus:**
```bash
# Enable local override (rename it back)
mv .claude/settings.local.json.disabled .claude/settings.local.json
```

### Method 2: Quick Toggle Script

Create a helper script to switch models easily:

```bash
# In project root
cat > switch-model.sh << 'EOF'
#!/bin/bash
if [ -f .claude/settings.local.json ]; then
  mv .claude/settings.local.json .claude/settings.local.json.disabled
  echo "✓ Switched to Sonnet 4.5 (default)"
else
  mv .claude/settings.local.json.disabled .claude/settings.local.json
  echo "✓ Switched to Opus 4.5 (override)"
fi
EOF

chmod +x switch-model.sh
```

Usage:
```bash
./switch-model.sh  # Toggle between models
```

### Method 3: Separate Complete Configs

If you want completely independent configurations:

```bash
# Create named configs
cp .claude/settings.json .claude/settings.sonnet.json
cp .claude/settings.json .claude/settings.opus.json

# Edit settings.opus.json to use Opus model
# Line 8: "model": "claude-opus-4-5-20251101"

# Switch to Opus
cp .claude/settings.opus.json .claude/settings.local.json

# Switch to Sonnet
rm .claude/settings.local.json  # Uses base settings.json
```

## Current Active Model

To check which model is currently active:

```bash
# Check if override is active
if [ -f .claude/settings.local.json ]; then
  echo "Active: Opus 4.5 (from settings.local.json)"
else
  echo "Active: Sonnet 4.5 (from settings.json)"
fi
```

Or within Claude Code:
- The model in use is shown in the status line
- Check the conversation metadata

## Model Comparison

| Model | ID | Best For |
|-------|-----|----------|
| **Sonnet 4.5** | `claude-sonnet-4-5-20250929` | Balanced performance & speed, recommended for most tasks |
| **Opus 4.5** | `claude-opus-4-5-20251101` | Maximum reasoning capability, complex problem-solving |
| **Haiku 4.5** | `claude-haiku-4-5-20251001` | Speed-optimized, simple tasks |

## Recommendations

- **Default (Sonnet)**: Use for daily development, testing, debugging
- **Opus**: Switch to when you need:
  - Complex architectural decisions
  - Advanced debugging of intricate issues
  - Deep code analysis
  - Complex refactoring tasks

## File Structure

```
.claude/
├── settings.json              # Base config (Sonnet)
├── settings.local.json        # Active override (Opus) - rename to disable
├── settings.local.json.disabled  # Disabled override
├── settings.sonnet.json       # Backup of Sonnet config (optional)
├── settings.opus.json         # Backup of Opus config (optional)
└── README.md                  # This file
```

## Notes

- `settings.local.json` is **not committed to git** (in `.gitignore`)
- Each developer can have their own local preferences
- Base `settings.json` is committed and shared across team
- Only the `preferences.model` field needs to differ between configs
