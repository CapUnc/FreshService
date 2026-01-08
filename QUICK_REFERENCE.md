# Freshservice Semantic Search - Quick Reference

## 🚀 Quick Start Commands

### Start Web Interface
```bash
cd "/Users/Sather/Documents/Python Programs/FreshService"
source .venv/bin/activate
streamlit run app.py --server.port 8501
```
**Access**: http://localhost:8501

### CLI Search Commands
```bash
# Free text search
python search_tickets.py "Teams video call problems"

# Ticket seed search  
python search_tickets.py --seed-ticket 4295

# Adjust similarity threshold
python search_tickets.py "Revit crashes" --max-distance 0.8

# Open result in browser
python search_tickets.py "Teams issues" --open 1
```

### Data Management
```bash
# Reingest all tickets
python freshservice.py

# Extract error messages from screenshots
python extract_error_messages.py --ticket 4295 --save
```

## 🎯 Distance Thresholds

| Threshold | Use Case | Results |
|-----------|----------|---------|
| 0.1 - 0.3 | Very precise matches | Few, high quality |
| 0.3 - 0.6 | **Default (0.55)** | Balanced |
| 0.6 - 0.8 | Broad search | More results |
| 0.8+ | Very broad | Many, loose matches |

## 🔍 Search Strategies

### Free Text Examples
```bash
"Revit crashes when opening files"
"Teams video calls not working" 
"Email not syncing on mobile"
"Bluebeam PDFs not opening"
"Enscape rendering errors"
```

### Ticket Seed Examples
```bash
# Find similar Enscape issues
python search_tickets.py --seed-ticket 4295

# Find similar Revit crashes
python search_tickets.py --seed-ticket 5160

# Find similar Teams problems
python search_tickets.py --seed-ticket 6427
```

## 📊 Current Database Stats

- **Total Tickets**: 3,947 closed incidents (after 2025-10-29 ingestion)
- **Range**: Ticket IDs 11 - 6501
- **Top Categories**: Software/Applications (1,503), Hardware (569), Microsoft Office 365 (408)
- **Top Subcategories**: Revit (367), Bluebeam (227), Teams (129), Enscape (95)

## 🛠️ Configuration Files

### api.env (Environment Variables)
```env
FRESHSERVICE_DOMAIN=cuninghamhelpdesk
FRESHSERVICE_PORTAL_DOMAIN=helpdesk.cuningham.com
FRESHSERVICE_API_KEY=your-api-key
OPENAI_API_KEY=your-openai-key
OPENAI_GUIDANCE_MODEL=gpt-4o-mini
OPENAI_SUMMARIZER_MODEL=gpt-4o-mini
FRESHSERVICE_TICKET_URL_TEMPLATE=https://{domain}/a/tickets/{ticket_id}
SEARCH_MAX_DISTANCE=0.55
CHROMA_COLLECTION_NAME=FreshService
CHROMA_TELEMETRY_IMPLEMENTATION=disabled
USE_AI_SUMMARY=0
INGEST_SINCE_DAYS=7
```

### Key Settings
- `SEARCH_MAX_DISTANCE=0.55` - Default similarity threshold
- `INGEST_STATUS_CODE=5` - Only closed tickets (status=5)
- `ENABLE_DESCRIPTION_CLEANING=1` - Clean ticket descriptions
- `INCLUDE_CONVERSATIONS_IN_EMBED=0` - Don't embed conversations
- `USE_AI_SUMMARY=0` - Opt in to AI-enhanced seed searches
- `INGEST_SINCE_DAYS=7` - Only ingest tickets updated in the last N days
- `CHROMA_TELEMETRY_IMPLEMENTATION=disabled` - Silence PostHog warnings from ChromaDB
- `FRESHSERVICE_TICKET_URL_TEMPLATE=...` - Override if your tenant uses a non-default deep link
- `FRESHSERVICE_PORTAL_DOMAIN=...` - Set when your agents use a custom helpdesk hostname

## 🔧 Common Troubleshooting

### No Results Found
```bash
# Try broader threshold
python search_tickets.py "your query" --max-distance 0.8

# Try simpler terms
python search_tickets.py "Revit"  # instead of complex error message
```

### Too Many Results
```bash
# Use more specific terms
python search_tickets.py "Revit crashes large files" --max-distance 0.3
```

### API Errors
```bash
# Test API connections
python -c "
from config import freshservice_session
import openai
import os
from dotenv import load_dotenv
load_dotenv('api.env')
print('Testing APIs...')
"
```

### ChromaDB Issues
```bash
# Fix version compatibility
pip install chromadb==0.4.22

# Recreate database if corrupted
rm -rf chroma_db/
python freshservice.py
```

## 📁 File Structure

```
FreshService/
├── README.md              # Main documentation
├── API_DOCUMENTATION.md   # Technical API docs
├── USER_GUIDE.md          # User instructions
├── TROUBLESHOOTING.md     # Problem solving
├── QUICK_REFERENCE.md     # This file
├── app.py                 # Streamlit web UI
├── search_tickets.py      # CLI search tool
├── freshservice.py        # Data ingestion
├── config.py              # Configuration
├── requirements.txt       # Dependencies
├── api.env               # Environment config
└── chroma_db/            # Database storage
```

## 🎯 Search Tips

### Effective Queries
- ✅ "Revit crashes when opening large files"
- ✅ "Teams video calls not working"
- ✅ "Email not syncing on mobile"
- ❌ "Computer broken"
- ❌ "Help me"

### Result Analysis
- **Distance 0.0000**: Exact match
- **Distance < 0.3**: Very similar
- **Distance 0.3-0.6**: Similar
- **Distance > 0.6**: Loosely related

### Metadata Usage
- **Agent**: Shows who handled similar issues
- **Group**: Indicates which team to escalate to
- **Category Path**: Shows problem classification
- **Priority**: Indicates severity level

## 🚨 Emergency Commands

### System Health Check
```bash
cd "/Users/Sather/Documents/Python Programs/FreshService"
source .venv/bin/activate
python -c "
import chromadb
client = chromadb.PersistentClient(path='./chroma_db')
collection = client.get_collection('FreshService')
print(f'Tickets: {len(collection.get()[\"ids\"])}')
"
```

### Complete Reset
```bash
# Backup
cp -r chroma_db chroma_db_backup_$(date +%Y%m%d_%H%M%S)

# Reset
rm -rf chroma_db/
python freshservice.py
```

### Quick Fixes
```bash
# Fix ChromaDB version
pip install chromadb==0.4.22

# Fix OpenAI version  
pip install openai==0.28.1

# Restart Streamlit
pkill -f streamlit
streamlit run app.py --server.port 8501
```

## 📞 Support Contacts

- **IT Help Desk Manager**: Primary contact
- **System Administrator**: Technical issues
- **Development Team**: Feature requests

## 📋 Useful Ticket IDs for Testing

- **4295**: Enscape Request (good for testing)
- **6427**: Teams video call issue
- **5160**: Revit crashes
- **3362**: Another Enscape issue
- **2416**: Revit crashing

---

**Last Updated**: January 2025  
**Version**: 1.0.0  
**Status**: Production Ready ✅
