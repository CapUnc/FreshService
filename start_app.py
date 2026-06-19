#!/usr/bin/env python3
"""
Startup script for Nexus with comprehensive diagnostics.
"""

import sys
import os
import subprocess
import argparse

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def check_virtual_environment():
    """Check if we're in a virtual environment."""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment detected")
        return True
    else:
        print("⚠️  No virtual environment detected")
        print("   Consider using: python -m venv .venv && source .venv/bin/activate")
        return False

def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = [
        ('streamlit', 'streamlit'),
        ('chromadb', 'chromadb'), 
        ('openai', 'openai'),
        ('requests', 'requests'),
        ('python-dotenv', 'dotenv'),
        ('beautifulsoup4', 'bs4')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} - not installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print("\n📦 Install missing packages:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_environment_file():
    """Check if environment configuration exists."""
    env_files = ['api.env', '.env']
    
    for env_file in env_files:
        if os.path.exists(env_file):
            print(f"✅ Found {env_file}")
            return True
    
    print("❌ No environment file found (api.env or .env)")
    print("   Create api.env with your Freshservice and OpenAI API keys")
    return False

def check_chromadb_database():
    """Check if ChromaDB database exists and is accessible."""
    try:
        from dotenv import load_dotenv
        load_dotenv('api.env') or load_dotenv()
        
        db_path = os.getenv('CHROMA_DB_PATH', './chroma_db')
        
        if not os.path.exists(db_path):
            print("❌ ChromaDB database not found")
            print(f"   Expected path: {db_path}")
            print("   Run: python freshservice.py to create the database")
            return False
        
        # Try to import and connect
        import chromadb
        client = chromadb.PersistentClient(path=db_path)
        collections = client.list_collections()
        
        if not collections:
            print("❌ No collections found in ChromaDB")
            print("   Run: python freshservice.py to populate the database")
            return False
        
        print(f"✅ ChromaDB database found with {len(collections)} collections")
        return True
        
    except Exception as e:
        print(f"❌ ChromaDB check failed: {e}")
        return False

def run_diagnostics():
    """Run comprehensive system diagnostics."""
    print("🔧 Running system diagnostics...")
    
    try:
        from debug_utils import SystemDiagnostics
        
        diagnostics = SystemDiagnostics().run_full_diagnostics()
        
        if diagnostics['errors']:
            print(f"\n❌ Found {len(diagnostics['errors'])} errors:")
            for error in diagnostics['errors']:
                print(f"   • {error}")
            return False
        elif diagnostics['warnings']:
            print(f"\n⚠️  Found {len(diagnostics['warnings'])} warnings:")
            for warning in diagnostics['warnings']:
                print(f"   • {warning}")
        
        print("✅ All diagnostics passed")
        return True
        
    except ImportError:
        print("⚠️  Diagnostics module not available")
        return True  # Don't fail if diagnostics aren't available
    except Exception as e:
        print(f"❌ Diagnostics failed: {e}")
        return False

def start_streamlit(port=8501, host="localhost"):
    """Start the Streamlit application."""
    print(f"\n🚀 Starting Streamlit app on {host}:{port}")
    
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.address", host,
        "--server.headless", "true"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Streamlit: {e}")
        return False
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        return True
    
    return True

def main():
    """Main startup function."""
    parser = argparse.ArgumentParser(description="Start Nexus")
    parser.add_argument("--port", type=int, default=8501, help="Port for Streamlit app")
    parser.add_argument("--host", default="localhost", help="Host for Streamlit app")
    parser.add_argument("--skip-checks", action="store_true", help="Skip system checks")
    parser.add_argument("--diagnostics-only", action="store_true", help="Run diagnostics only")
    
    args = parser.parse_args()
    
    print("🔎 Nexus - Startup Check")
    print("=" * 50)
    
    if not args.skip_checks:
        checks_passed = 0
        total_checks = 5
        
        if check_python_version():
            checks_passed += 1
        
        if check_virtual_environment():
            checks_passed += 1
        
        if check_dependencies():
            checks_passed += 1
        
        if check_environment_file():
            checks_passed += 1
        
        if check_chromadb_database():
            checks_passed += 1
        
        print(f"\n📊 System Check Results: {checks_passed}/{total_checks} passed")
        
        if checks_passed < total_checks:
            print("\n❌ Some checks failed. Please resolve issues before starting.")
            print("\n💡 Common solutions:")
            print("   • Install dependencies: pip install -r requirements.txt")
            print("   • Create api.env with your API keys")
            print("   • Run data ingestion: python freshservice.py")
            print("   • Use virtual environment: source .venv/bin/activate")
            return 1
    
    # Run diagnostics
    if not run_diagnostics():
        print("\n❌ System diagnostics failed")
        return 1
    
    if args.diagnostics_only:
        print("\n✅ Diagnostics complete")
        return 0
    
    # Start the application
    print("\n✅ All checks passed! Starting application...")
    
    if not start_streamlit(args.port, args.host):
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
