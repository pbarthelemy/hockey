#!/bin/bash

# Quick start script for Hockey Scoresheet Analyzer

echo "🏒 Starting Hockey Scoresheet Analyzer..."
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

echo "🚀 Starting server on http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

npm start
