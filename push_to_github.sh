#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "================================================="
echo "   Push Slack Auto-Reply Bot to Private GitHub"
echo "================================================="
echo ""
echo "Step 1: Go to https://github.com/new and create a new PRIVATE repository (e.g. slack-auto-reply-bot)."
echo ""
read -p "Step 2: Paste your GitHub repository URL here (e.g. https://github.com/username/slack-auto-reply-bot.git): " REPO_URL

if [ -z "$REPO_URL" ]; then
  echo "❌ Repository URL cannot be empty."
  exit 1
fi

git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git branch -M main

echo "Pushing to $REPO_URL..."
git push -u origin main

echo ""
echo "🎉 SUCCESS: Code has been pushed to your private GitHub repository!"
echo ""
echo "Next step: Connect this repo to Railway (https://railway.app) or Render (https://render.com)!"
