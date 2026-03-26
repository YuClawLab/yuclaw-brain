#!/bin/bash
# YUCLAW OpenClaw Skill — one command install

echo "Installing YUCLAW skill for OpenClaw..."

mkdir -p ~/.openclaw/skills/yuclaw-financial

curl -s -o ~/.openclaw/skills/yuclaw-financial/index.js \
  https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/yuclaw/openclaw/skill.js

echo '{"name":"yuclaw-financial","version":"1.1.0","main":"index.js"}' > \
  ~/.openclaw/skills/yuclaw-financial/package.json

echo "YUCLAW skill installed"
echo ""
echo "Restart OpenClaw: openclaw restart"
echo "Then try: /yuclaw signals"
