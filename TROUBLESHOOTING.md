# 🔧 Troubleshooting Guide

This guide helps you resolve common issues with the Freshservice Semantic Search system.

## 🚀 Quick Start

### Start the Application
```bash
# Method 1: Using the startup script (recommended)
python start_app.py

# Method 2: Direct Streamlit
streamlit run app.py

# Method 3: With custom port
python start_app.py --port 8503
```

### Run Diagnostics
```bash
# Run system diagnostics only
python start_app.py --diagnostics-only

# Run comprehensive troubleshooting
python troubleshoot.py
```

## 🚨 Common Issues & Solutions

### 1. ChromaDB Import Errors

**Error:** `ImportError: cannot import name 'SubmitEmbeddingRecord' from 'chromadb.types'`

**Cause:** Version incompatibility between ChromaDB and other packages.

**Solution:**
```bash
# Fix ChromaDB version
pip uninstall chromadb -y
pip install chromadb==0.4.22

# Fix NumPy compatibility
pip install 'numpy>=1.22.5,<2.0' --force-reinstall
```

### 2. OpenAI API Errors

**Error:** `Incorrect API key provided` or `'$.input' is invalid`

**Cause:** Invalid or missing OpenAI API key.

**Solution:**
1. Check your `api.env` file:
```bash
cat api.env | grep OPENAI_API_KEY
```

2. Update with a valid key:
```bash
echo "OPENAI_API_KEY=sk-your-valid-key-here" >> api.env
```

3. Test the key:
```bash
python -c "
import openai
import os
from dotenv import load_dotenv
load_dotenv('api.env')
openai.api_key = os.getenv('OPENAI_API_KEY')
response = openai.Embedding.create(input='test', model='text-embedding-3-small')
print('✅ API key is valid')
"
```

### 3. Streamlit Dependency Conflicts

**Error:** `ImportError` or version conflicts in Streamlit

**Cause:** Incompatible package versions.

**Solution:**
```bash
# Fix Streamlit dependencies
pip install 'h11<0.15,>=0.13' 'packaging<25,>=20' 'protobuf<6,>=3.20' 'rich<14,>=10.14.0' 'tenacity<9,>=8.1.0' --force-reinstall
```

### 4. Database Not Found

**Error:** `ChromaDB database not found` or empty search results

**Cause:** Database not created or corrupted.

**Solution:**
```bash
# Recreate the database
rm -rf chroma_db
python freshservice.py
```

### 5. Port Already in Use

**Error:** `Port 8501 is already in use`

**Cause:** Another Streamlit instance is running.

**Solution:**
```bash
# Kill existing processes
pkill -f streamlit

# Or use a different port
python start_app.py --port 8503
```

### 6. Permission Denied

**Error:** `Permission denied` when accessing files

**Cause:** File permission issues.

**Solution:**
```bash
# Fix permissions
chmod -R 755 .
chmod +x start_app.py troubleshoot.py

# Or run with sudo (not recommended)
sudo python start_app.py
```

## 🔍 Debugging Tools

### System Diagnostics
```bash
# Run comprehensive diagnostics
python debug_utils.py

# Check specific components
python -c "
from debug_utils import SystemDiagnostics
diag = SystemDiagnostics()
print('ChromaDB:', diag.check_chromadb_connection())
print('OpenAI:', diag.check_openai_connection())
"
```

### Log Files
Check these files for detailed error information:
- `freshservice_debug.log` - Application logs
- Terminal output - Real-time errors
- Streamlit logs - Web interface errors

### Debug Mode in Streamlit
Enable debug mode in the web interface:
1. Open the Streamlit app
2. Check "🔧 Debug Mode" in the sidebar
3. View detailed error information and system status

## 🛠️ Advanced Troubleshooting

### Complete System Reset
If all else fails, reset the entire system:

```bash
# 1. Stop all processes
pkill -f streamlit
pkill -f python

# 2. Remove virtual environment
rm -rf .venv

# 3. Recreate virtual environment
python -m venv .venv
source .venv/bin/activate

# 4. Reinstall dependencies
pip install -r requirements.txt

# 5. Recreate database
rm -rf chroma_db
python freshservice.py

# 6. Test system
python start_app.py --diagnostics-only
```

### Environment Issues
Check your environment configuration:

```bash
# Check Python version (3.8+ required)
python --version

# Check virtual environment
echo $VIRTUAL_ENV

# Check environment variables
python -c "
import os
from dotenv import load_dotenv
load_dotenv('api.env')
print('FRESHSERVICE_DOMAIN:', os.getenv('FRESHSERVICE_DOMAIN'))
print('CHROMA_DB_PATH:', os.getenv('CHROMA_DB_PATH'))
print('CHROMA_COLLECTION_NAME:', os.getenv('CHROMA_COLLECTION_NAME'))
"
```

### Network Issues
If you're having connectivity issues:

```bash
# Test Freshservice API
python -c "
import requests
import os
from dotenv import load_dotenv
load_dotenv('api.env')

domain = os.getenv('FRESHSERVICE_DOMAIN')
api_key = os.getenv('FRESHSERVICE_API_KEY')

response = requests.get(f'https://{domain}/api/v2/tickets', 
                       headers={'Authorization': f'Basic {api_key}'})
print('Freshservice API:', response.status_code)
"

# Test OpenAI API
python -c "
import openai
import os
from dotenv import load_dotenv
load_dotenv('api.env')

openai.api_key = os.getenv('OPENAI_API_KEY')
response = openai.Embedding.create(input='test', model='text-embedding-3-small')
print('OpenAI API: Working')
"
```

## 📞 Getting Help

If you're still having issues:

1. **Run the troubleshooting script:**
   ```bash
   python troubleshoot.py
   ```

2. **Check the logs:**
   ```bash
   tail -f freshservice_debug.log
   ```

3. **Enable debug mode** in the Streamlit interface

4. **Collect system information:**
   ```bash
   python start_app.py --diagnostics-only > diagnostics.txt 2>&1
   ```

## 🔧 Maintenance Commands

### Regular Maintenance
```bash
# Check system health
python start_app.py --diagnostics-only

# Update data (if needed)
python freshservice.py

# Clean up logs
rm -f freshservice_debug.log

# Backup database
cp -r chroma_db chroma_db_backup_$(date +%Y%m%d)
```

### Performance Issues
```bash
# Check database size
du -sh chroma_db/

# Check memory usage
ps aux | grep python

# Monitor logs in real-time
tail -f freshservice_debug.log
```

## ✅ Success Indicators

Your system is working correctly when:
- ✅ All imports succeed without errors
- ✅ ChromaDB connects and shows ticket count > 0
- ✅ OpenAI API responds to test calls
- ✅ Streamlit starts without import errors
- ✅ Search returns relevant results
- ✅ No errors in debug logs

## 🎯 Next Steps After Fixing Issues

1. **Test the system:**
   ```bash
   python search_tickets.py "test query"
   ```

2. **Start the web interface:**
   ```bash
   python start_app.py
   ```

3. **Verify search functionality** with known ticket IDs

4. **Check data quality** in the web interface

Remember: Most issues are resolved by ensuring compatible package versions and proper environment configuration.