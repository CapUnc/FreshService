#!/bin/bash
# Auto-push script that waits for repository to be created, then pushes

echo "🔍 Monitoring for GitHub repository..."
echo "📍 Remote: git@github.com:CapUnc/FreshService.git"
echo ""

# Open GitHub creation page
open "https://github.com/new?name=FreshService&description=A+powerful+semantic+search+tool+for+Freshservice+tickets&visibility=public" 2>&1

echo "📝 Please create the repository on GitHub:"
echo "   1. Name: FreshService"
echo "   2. Visibility: Public (or Private)"
echo "   3. DO NOT initialize with README, .gitignore, or license"
echo "   4. Click 'Create repository'"
echo ""
echo "⏳ Waiting for repository to be created..."
echo "   (Checking every 5 seconds...)"
echo ""

# Poll for repository existence
MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if git ls-remote --exit-code origin &>/dev/null 2>&1; then
        echo ""
        echo "✅ Repository found! Pushing code..."
        echo ""
        git push -u origin main
        if [ $? -eq 0 ]; then
            echo ""
            echo "🎉 Successfully pushed to GitHub!"
            echo "📍 View at: https://github.com/CapUnc/FreshService"
            exit 0
        else
            echo ""
            echo "❌ Push failed. Please check your permissions."
            exit 1
        fi
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    if [ $((ATTEMPT % 6)) -eq 0 ]; then
        echo "   Still waiting... ($ATTEMPT/60 attempts)"
    fi
    sleep 5
done

echo ""
echo "⏱️  Timeout: Repository not created after 5 minutes."
echo "   Please create it manually and run: git push -u origin main"
exit 1

