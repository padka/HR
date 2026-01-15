#!/bin/bash

# Quick test script for modal functionality

echo "🧪 Testing modal functionality"
echo "================================"
echo ""

# Open test HTML in browser
if command -v open &> /dev/null; then
    echo "✅ Opening test file in browser (macOS)..."
    open test_modal.html
elif command -v xdg-open &> /dev/null; then
    echo "✅ Opening test file in browser (Linux)..."
    xdg-open test_modal.html
elif command -v start &> /dev/null; then
    echo "✅ Opening test file in browser (Windows)..."
    start test_modal.html
else
    echo "❌ Cannot detect browser opener"
    echo "   Please open test_modal.html manually in your browser"
fi

echo ""
echo "📋 Test checklist:"
echo "   1. ✓ Page loads and shows two buttons"
echo "   2. ✓ 'Один слот' modal opens automatically"
echo "   3. ✓ Click 'Серия' button - should switch modals"
echo "   4. ✓ Click backdrop or × to close"
echo "   5. ✓ Press ESC to close modal"
echo "   6. ✓ Check browser console for detailed logs"
echo ""
echo "💡 If test page works but main page doesn't:"
echo "   - Check CSP (Content Security Policy) errors"
echo "   - Check if nonce is correctly set on main page"
echo "   - Check if script tag is present and not blocked"
echo ""
