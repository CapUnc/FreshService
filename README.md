# 🔎 Freshservice Semantic Search

A powerful semantic search tool for Freshservice tickets that enables IT help desk teams to quickly find relevant historical incidents and solutions using AI-enhanced natural language queries and ticket-based seeding.

## 🚀 Features

- **🤖 AI-Enhanced Search**: AI-powered summarization for better semantic matching
- **Semantic Search**: Find relevant tickets using natural language queries
- **Ticket Seeding**: Start searches from specific ticket IDs to find similar issues
- **Hybrid Search**: Combines free text and ticket-based search capabilities
- **Clean Data**: Automated text cleaning removes signatures and reply chains
- **Rich Metadata**: Full categorization, agent attribution, and ticket details
- **Web UI**: Streamlit-based interface with debug mode and AI toggles
- **On-Demand AI Guidance**: One-click OpenAI recommendations for next steps, categories, and assignment groups
- **CLI Interface**: Command-line tool for power users
- **Vision Helper**: Extract error messages from screenshots using OpenAI Vision
- **🔧 Error Handling**: Comprehensive diagnostics and troubleshooting tools
- **Smart Startup**: Automated system validation and health checks

## 📊 Current Status

✅ **Fully Operational** - 3,660 closed incident tickets indexed and searchable

### Database Statistics
- **Total Tickets**: 3,660 closed incidents
- **Ticket Range**: 11 - 6501
- **Top Categories**: Software/Applications (1,503), Hardware (569), Microsoft Office 365 (408)
- **Top Subcategories**: Revit (367), Bluebeam (227), Teams (129), Enscape (95)

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Freshservice API access
- OpenAI API key

### Smart Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd FreshService

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables in api.env
cp api.env.example api.env
# Edit api.env with your API keys

# Smart startup with system validation
python start_app.py
```

### Manual Setup
1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables in `api.env`:
   ```env
   FRESHSERVICE_DOMAIN=your-domain.freshservice.com
   FRESHSERVICE_API_KEY=your-api-key
   OPENAI_API_KEY=your-openai-key
   ```

### First Run
```bash
# Populate database with closed tickets
python freshservice.py

# Start with smart validation
python start_app.py

# Or run diagnostics only
python start_app.py --diagnostics-only
```

## 🔧 Configuration

### Environment Variables (`api.env`)

#### Freshservice Configuration
- `FRESHSERVICE_DOMAIN`: Your Freshservice domain (e.g., `cuninghamhelpdesk.freshservice.com`)
- `FRESHSERVICE_API_KEY`: Your Freshservice API key
- `REQUEST_TIMEOUT_SECONDS`: API request timeout (default: 30)
- `RATE_LIMIT_SLEEP_SECONDS`: Rate limiting delay (default: 0.1)

#### OpenAI Configuration
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_EMBEDDING_MODEL`: Embedding model (default: `text-embedding-3-small`)
- `OPENAI_VISION_MODEL`: Vision model (default: `gpt-4o-mini`)

#### ChromaDB Configuration
- `CHROMA_DB_PATH`: Database path (default: `./chroma_db`)
- `CHROMA_COLLECTION_NAME`: Collection name (default: `FreshService`)

#### Search Configuration
- `SEARCH_MAX_DISTANCE`: Default similarity threshold (default: 0.55)
- `SEARCH_MAX_DISPLAY`: Results to display (default: 5)

#### Ingest Configuration
- `INGEST_STATUS_CODE`: Ticket status filter (default: 5 = Closed)
- `INGEST_MAX_TOKENS`: Max tokens per ticket (default: 3000)
- `INCLUDE_CONVERSATIONS_IN_EMBED`: Include conversations in embeddings (default: 0)
- `ENABLE_DESCRIPTION_CLEANING`: Clean ticket descriptions (default: 1)

## 📖 Usage

### Command Line Interface

#### Free Text Search
```bash
python search_tickets.py "Teams video call problems" --max-distance 0.8
```

#### Ticket Seed Search (AI-Enhanced by Default)
```bash
# AI-enhanced search (recommended)
python search_tickets.py --seed-ticket 4295 --max-distance 0.9

# Raw text search (no AI)
python search_tickets.py --seed-ticket 4295 --no-ai-summary --max-distance 0.9
```

#### Search Options
- `--max-distance`: Similarity threshold (0.0 = exact match, higher = more results)
- `--no-clean-seed`: Use raw description instead of cleaned version
- `--no-ai-summary`: Disable AI summarization (use raw text)
- `--open`: Open top result in browser
- `--require-token`: Keep only tickets that mention the same high-signal software terms
- `--same-category-only`: (Seeded searches) restrict to tickets in the same category path

### Web Interface

#### Smart Startup (Recommended)
```bash
python start_app.py --port 8501
```

#### Manual Startup
```bash
streamlit run app.py --server.port 8501
```

Access at: http://localhost:8501

#### Web UI Features
- **🤖 AI-Enhanced Search**: Toggle AI summarization for better results
- **Search Types**: Free text or ticket seeding
- **Distance Threshold**: Adjustable similarity cutoff (default: 0.9)
- **Result Filtering**: Bucket results by similarity (Most Similar, Similar, Related, Loose)
- **Strict Filters**: Optional toggles to require exact software term matches or limit to the seeded ticket's category
- **AI Guidance Button**: Generate next steps, category, and assignment group recommendations on demand
- **Metadata Display**: Full ticket details, agent info, category paths
- **Description Views**: Toggle between cleaned and original descriptions
- **🔧 Debug Mode**: Comprehensive system diagnostics and error information
- **AI Status**: Shows whether search is AI-enhanced or using raw text

### Data Ingestion

To reingest or update the database:
```bash
python freshservice.py
```

This will:
- Fetch closed incidents from Freshservice
- Clean and process ticket descriptions
- Generate embeddings using OpenAI
- Store in ChromaDB for fast retrieval

### Vision Helper

Extract error messages from ticket screenshots:
```bash
python extract_error_messages.py --ticket 4295
```

Options:
- `--save`: Save processed images for QA
- `--model`: Override vision model

## 🎯 Search Strategies

### Distance Thresholds
- **0.3**: Very precise matches (fewer results, higher quality)
- **0.55**: Balanced precision/recall (recommended default)
- **0.8**: Broad search (more results, includes loosely related)

### Search Types
1. **Free Text**: Best for discovering general problems
   - "Revit crashes and freezes"
   - "Teams video call issues"
   - "Email not working"

2. **Ticket Seeding**: Best for finding similar specific issues
   - Start with a known ticket ID
   - Find tickets with similar problems
   - Great for escalation and pattern recognition

### Category-Based Search
The system automatically categorizes tickets:
- **Software/Applications**: Revit, Bluebeam, Enscape, etc.
- **Hardware**: Computers, docking stations, peripherals
- **Microsoft Office 365**: Teams, Outlook, SharePoint
- **Network**: Connectivity, VPN, remote access
- **Account and Access**: Login issues, permissions

## 🔍 Advanced Features

### Text Cleaning
- Removes email signatures and reply chains
- Strips HTML formatting
- Normalizes whitespace
- Preserves technical content

### Agent Resolution
- Resolves agent IDs to names
- Handles group assignments
- Caches agent information
- Fallback to "Unknown" for missing data

### Metadata Enrichment
- Full category paths (Category → Subcategory → Item)
- Priority and status information
- Requester details
- Resolution timestamps

## 🚨 Troubleshooting

### Smart Troubleshooting Tools

#### Interactive Troubleshooting
```bash
python troubleshoot.py
```
This provides an interactive menu to fix common issues automatically.

#### System Diagnostics
```bash
python start_app.py --diagnostics-only
```
Runs comprehensive system health checks and validation.

#### Debug Mode
Enable debug mode in the Streamlit sidebar to see detailed error information and system status.

### Common Issues

#### ChromaDB Import Errors
```bash
pip install chromadb==0.4.22
```

#### OpenAI API Errors
- Verify API key is valid and has sufficient credits
- Check rate limiting settings
- Ensure model names are correct
- AI summarization will gracefully fall back to raw text if it fails

#### Freshservice API Errors
- Verify domain and API key
- Check network connectivity
- Review rate limiting settings

#### Empty Search Results
- Try increasing `--max-distance` threshold (default is now 0.9)
- Check if query terms are too specific
- Verify database has been properly ingested
- Enable AI-enhanced search for better results

#### AI Enhancement Issues
- System automatically falls back to raw text if AI fails
- Check OpenAI API key and credits
- Use `--no-ai-summary` flag to disable AI enhancement

### Performance Optimization

#### AI Enhancement Benefits
- **Improved Results**: +11% more comprehensive search results
- **Better Relevance**: AI expands technical terms and focuses on core issues
- **Semantic Matching**: Enhanced bridges between new and historical tickets
- **Fallback Safety**: Graceful degradation to raw text if AI fails

#### Database Size
- Current: 3,660 tickets (~93MB)
- Search time: <1 second for most queries
- Memory usage: ~200MB during operation
- AI costs: ~$0.001 per search (GPT-3.5-turbo)

#### Rate Limiting
- Freshservice: 100 requests/minute (configurable)
- OpenAI: 3,000 requests/minute (tier dependent)

## 📁 Project Structure

```
FreshService/
├── app.py                    # Streamlit web interface
├── config.py                # Configuration and API clients
├── freshservice.py          # Data ingestion script
├── search_tickets.py        # CLI search interface
├── ai_summarizer.py         # AI-powered ticket summarization
├── extract_error_messages.py # Vision helper
├── text_cleaning.py         # Text preprocessing
├── start_app.py             # Smart startup script
├── troubleshoot.py          # Interactive troubleshooting tool
├── debug_utils.py           # System diagnostics and error handling
├── requirements.txt         # Python dependencies
├── api.env                  # Environment configuration
├── chroma_db/               # ChromaDB storage
└── ticket_images/           # Screenshot storage
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is proprietary software for Cuningham's IT help desk operations.

## 📞 Support

For technical support or questions:
- IT Help Desk Manager
- Internal documentation and runbooks
- System logs in `/Users/Sather/Documents/Python Programs/FreshService/logs/`

---

**Last Updated**: January 2025  
**Version**: 2.0.0  
**Status**: Production Ready with AI Enhancement ✅
