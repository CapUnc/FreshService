#!/bin/bash
# Helper script to push to GitHub after repository is created

echo "🚀 Pushing FreshService to GitHub..."
echo ""

# Check if remote is configured
if ! git remote get-url origin &>/dev/null; then
    echo "❌ Remote 'origin' not configured"
    exit 1
fi

# Check if repository exists on GitHub
echo "Checking if repository exists on GitHub..."
if git ls-remote --exit-code origin &>/dev/null; then
    echo "✅ Repository exists on GitHub"
    echo ""
    echo "Pushing commits..."
    git push -u origin main
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Successfully pushed to GitHub!"
        echo "📍 Repository: https://github.com/CapUnc/FreshService"
    else
        echo ""
        echo "❌ Failed to push. Please check your permissions."
    fi
else
    echo ""
    echo "⚠️  Repository doesn't exist yet on GitHub."
    echo ""
    echo "Please:"
    echo "1. Create the repository at: https://github.com/new"
    echo "   - Name: FreshService"
    echo "   - Visibility: Public (or Private)"
    echo "   - DO NOT initialize with README, .gitignore, or license"
    echo ""
    echo "2. Then run this script again, or run:"
    echo "   git push -u origin main"
    echo ""
    echo "Or open this URL to create with pre-filled info:"
    echo "https://github.com/new?name=FreshService&description=A+powerful+semantic+search+tool+for+Freshservice+tickets&visibility=public"
fi

