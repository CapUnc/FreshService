# =========================
# File: debug_utils.py
# Debug utilities and error handling for Freshservice Semantic Search
# =========================

import os
import sys
import traceback
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import streamlit as st

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('freshservice_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class SystemDiagnostics:
    """Comprehensive system diagnostics and error handling."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
    
    def check_environment(self) -> Dict[str, Any]:
        """Check environment variables and configuration."""
        results = {
            'env_vars': {},
            'python_version': sys.version,
            'working_directory': os.getcwd(),
            'timestamp': datetime.now().isoformat()
        }
        
        # Check critical environment variables
        critical_vars = [
            'FRESHSERVICE_DOMAIN',
            'FRESHSERVICE_API_KEY', 
            'OPENAI_API_KEY',
            'CHROMA_DB_PATH',
            'CHROMA_COLLECTION_NAME'
        ]
        
        for var in critical_vars:
            value = os.getenv(var)
            if value:
                # Mask sensitive values
                if 'API_KEY' in var or 'SECRET' in var:
                    masked_value = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
                    results['env_vars'][var] = masked_value
                else:
                    results['env_vars'][var] = value
            else:
                self.errors.append(f"Missing environment variable: {var}")
                results['env_vars'][var] = None
        
        return results
    
    def check_dependencies(self) -> Dict[str, Any]:
        """Check if all required dependencies are available."""
        results = {
            'imports': {},
            'versions': {}
        }
        
        # Check critical imports
        critical_imports = [
            ('chromadb', 'ChromaDB'),
            ('openai', 'OpenAI'),
            ('streamlit', 'Streamlit'),
            ('requests', 'HTTP requests'),
            ('dotenv', 'Environment loading')
        ]
        
        for module, description in critical_imports:
            try:
                imported_module = __import__(module)
                results['imports'][module] = {
                    'status': 'success',
                    'description': description,
                    'version': getattr(imported_module, '__version__', 'unknown')
                }
                results['versions'][module] = getattr(imported_module, '__version__', 'unknown')
            except ImportError as e:
                error_msg = f"Failed to import {module}: {str(e)}"
                self.errors.append(error_msg)
                results['imports'][module] = {
                    'status': 'error',
                    'description': description,
                    'error': str(e)
                }
        
        return results
    
    def check_chromadb_connection(self) -> Dict[str, Any]:
        """Test ChromaDB connection and database integrity."""
        results = {
            'connection': 'unknown',
            'database_path': None,
            'collection_count': 0,
            'ticket_count': 0,
            'errors': []
        }
        
        try:
            import chromadb
            from dotenv import load_dotenv
            
            # Load environment
            load_dotenv('api.env') or load_dotenv()
            
            db_path = os.getenv('CHROMA_DB_PATH', './chroma_db')
            collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'FreshService')
            
            results['database_path'] = db_path
            
            # Test connection
            if not os.path.exists(db_path):
                error_msg = f"ChromaDB path does not exist: {db_path}"
                self.errors.append(error_msg)
                results['errors'].append(error_msg)
                results['connection'] = 'failed'
                return results
            
            # Try to connect
            client = chromadb.PersistentClient(path=db_path)
            results['connection'] = 'success'
            
            # Get collections
            collections = client.list_collections()
            results['collection_count'] = len(collections)
            
            # Test collection access
            if collections:
                collection = client.get_collection(collection_name)
                results['ticket_count'] = len(collection.get()['ids'])
                
        except Exception as e:
            error_msg = f"ChromaDB connection failed: {str(e)}"
            self.errors.append(error_msg)
            results['errors'].append(error_msg)
            results['connection'] = 'failed'
            logger.error(f"ChromaDB error: {traceback.format_exc()}")
        
        return results
    
    def check_openai_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection."""
        results = {
            'connection': 'unknown',
            'model_available': False,
            'api_key_valid': False,
            'errors': []
        }
        
        try:
            import openai
            from dotenv import load_dotenv
            
            # Load environment
            load_dotenv('api.env') or load_dotenv()
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                error_msg = "OpenAI API key not found"
                self.errors.append(error_msg)
                results['errors'].append(error_msg)
                return results
            
            # Test API key
            openai.api_key = api_key
            
            # Simple test call
            response = openai.Embedding.create(
                input="test",
                model="text-embedding-3-small"
            )
            
            results['connection'] = 'success'
            results['api_key_valid'] = True
            results['model_available'] = True
            
        except Exception as e:
            error_msg = f"OpenAI connection failed: {str(e)}"
            self.errors.append(error_msg)
            results['errors'].append(error_msg)
            results['connection'] = 'failed'
            logger.error(f"OpenAI error: {traceback.format_exc()}")
        
        return results
    
    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Run complete system diagnostics."""
        logger.info("Starting full system diagnostics...")
        
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.check_environment(),
            'dependencies': self.check_dependencies(),
            'chromadb': self.check_chromadb_connection(),
            'openai': self.check_openai_connection(),
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }
        
        # Log summary
        if self.errors:
            logger.error(f"Diagnostics found {len(self.errors)} errors")
            for error in self.errors:
                logger.error(f"ERROR: {error}")
        
        if self.warnings:
            logger.warning(f"Diagnostics found {len(self.warnings)} warnings")
            for warning in self.warnings:
                logger.warning(f"WARNING: {warning}")
        
        if not self.errors:
            logger.info("System diagnostics passed - all components healthy")
        
        return diagnostics

def safe_import(module_name: str, description: str = None) -> Optional[Any]:
    """Safely import a module with error handling."""
    try:
        return __import__(module_name)
    except ImportError as e:
        error_msg = f"Failed to import {module_name}: {str(e)}"
        if description:
            error_msg += f" (Required for: {description})"
        logger.error(error_msg)
        return None
    except Exception as e:
        error_msg = f"Unexpected error importing {module_name}: {str(e)}"
        logger.error(error_msg)
        return None

def handle_streamlit_error(func):
    """Decorator for handling errors in Streamlit functions."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_details = {
                'function': func.__name__,
                'error': str(e),
                'traceback': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.error(f"Streamlit error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Display user-friendly error in Streamlit
            st.error(f"❌ Error in {func.__name__}: {str(e)}")
            
            # Show debug info if in debug mode
            if st.session_state.get('debug_mode', False):
                with st.expander("🔧 Debug Information"):
                    st.json(error_details)
                    st.code(traceback.format_exc())
            
            return None
    return wrapper

def display_system_status():
    """Display system status in Streamlit."""
    diagnostics = SystemDiagnostics().run_full_diagnostics()
    
    # Status indicators
    if diagnostics['errors']:
        st.error(f"🚨 System has {len(diagnostics['errors'])} errors")
    else:
        st.success("✅ System healthy")
    
    # Show detailed diagnostics
    with st.expander("🔧 System Diagnostics"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Environment")
            env = diagnostics['environment']
            st.write(f"Python: {env['python_version'].split()[0]}")
            st.write(f"Working Directory: {env['working_directory']}")
            
            st.subheader("Dependencies")
            for module, info in diagnostics['dependencies']['imports'].items():
                if info['status'] == 'success':
                    st.success(f"✅ {module} ({info['version']})")
                else:
                    st.error(f"❌ {module}: {info['error']}")
        
        with col2:
            st.subheader("ChromaDB")
            chromadb_info = diagnostics['chromadb']
            if chromadb_info['connection'] == 'success':
                st.success(f"✅ Connected to {chromadb_info['database_path']}")
                st.write(f"Collections: {chromadb_info['collection_count']}")
                st.write(f"Tickets: {chromadb_info['ticket_count']}")
            else:
                st.error("❌ ChromaDB connection failed")
                for error in chromadb_info['errors']:
                    st.error(f"• {error}")
            
            st.subheader("OpenAI")
            openai_info = diagnostics['openai']
            if openai_info['connection'] == 'success':
                st.success("✅ OpenAI API connected")
            else:
                st.error("❌ OpenAI connection failed")
                for error in openai_info['errors']:
                    st.error(f"• {error}")
        
        # Show errors if any
        if diagnostics['errors']:
            st.subheader("🚨 Errors")
            for error in diagnostics['errors']:
                st.error(f"• {error}")
        
        # Show warnings if any
        if diagnostics['warnings']:
            st.subheader("⚠️ Warnings")
            for warning in diagnostics['warnings']:
                st.warning(f"• {warning}")

if __name__ == "__main__":
    # Run diagnostics when called directly
    diagnostics = SystemDiagnostics().run_full_diagnostics()
    print("\n=== SYSTEM DIAGNOSTICS ===")
    print(f"Timestamp: {diagnostics['timestamp']}")
    print(f"Errors: {len(diagnostics['errors'])}")
    print(f"Warnings: {len(diagnostics['warnings'])}")
    
    if diagnostics['errors']:
        print("\nErrors:")
        for error in diagnostics['errors']:
            print(f"  ❌ {error}")
    
    if diagnostics['warnings']:
        print("\nWarnings:")
        for warning in diagnostics['warnings']:
            print(f"  ⚠️ {warning}")
    
    if not diagnostics['errors'] and not diagnostics['warnings']:
        print("\n✅ All systems healthy!")
