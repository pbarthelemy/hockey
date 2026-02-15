#!/bin/bash

# Setup script for Hockey Scoresheet Analyzer

echo "================================"
echo "Hockey Scoresheet Analyzer Setup"
echo "================================"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed."
    echo ""
    echo "To install Node.js on Ubuntu/Debian:"
    echo "  sudo apt update"
    echo "  sudo apt install nodejs npm"
    echo ""
    echo "Or install via nvm (recommended):"
    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
    echo "  nvm install --lts"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"
echo "✅ npm version: $(npm --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "To start the application:"
    echo "  npm start"
    echo ""
    echo "Then open your browser to:"
    echo "  http://localhost:3000"
else
    echo ""
    echo "❌ Installation failed!"
    exit 1
fi
