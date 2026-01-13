#!/bin/bash

echo "🔍 Debugging MCP Setup..."

# Check Python version
echo "Python version:"
python --version

# Check if MCP is installed
echo -e "\n📦 Checking MCP installation:"
pip list | grep mcp || echo "❌ MCP not found"

# Check MCP version specifically
echo -e "\n🔍 MCP package details:"
pip show mcp 2>/dev/null || echo "❌ MCP package not installed"

# Install/upgrade MCP
echo -e "\n📥 Installing/upgrading MCP..."
pip install --upgrade mcp

# Alternative installation methods
echo -e "\n🔄 Trying alternative installations..."
pip install --upgrade model-context-protocol
pip install --upgrade "mcp[server]"

# Check what got installed
echo -e "\n✅ Final package check:"
pip list | grep -E "(mcp|model-context)"

# Create a minimal test
echo -e "\n🧪 Creating minimal test..."

cat > test_mcp_imports.py << 'EOF'
#!/usr/bin/env python3
print("Testing MCP imports...")

try:
    import mcp
    print(f"✅ mcp imported successfully, version: {getattr(mcp, '__version__', 'unknown')}")
except ImportError as e:
    print(f"❌ Failed to import mcp: {e}")

try:
    from mcp.server import Server
    print("✅ Server imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Server: {e}")

try:
    from mcp.server.stdio import stdio_server
    print("✅ stdio_server imported successfully")
except ImportError as e:
    print(f"❌ Failed to import stdio_server: {e}")

try:
    from mcp.types import Tool, TextContent, CallToolResult
    print("✅ Types imported successfully")
except ImportError as e:
    print(f"❌ Failed to import types: {e}")

print("\n📋 Available modules in mcp package:")
try:
    import pkgutil
    import mcp
    for importer, modname, ispkg in pkgutil.iter_modules(mcp.__path__, mcp.__name__ + "."):
        print(f"  - {modname}")
except:
    print("  Could not list modules")

EOF

python test_mcp_imports.py

echo -e "\n🎯 Next steps:"
echo "1. If imports failed, try: pip install --force-reinstall mcp"
echo "2. If still failing, try: pip install fastmcp"
echo "3. Check Python path: python -c 'import sys; print(sys.path)'"