# Freshservice Semantic Search v2.0 - API Documentation

## Overview

This document provides detailed API documentation for the Freshservice Semantic Search system, including configuration options, search parameters, AI enhancement features, and integration details.

## Configuration API

### Environment Variables

#### Freshservice Configuration
```env
FRESHSERVICE_DOMAIN=cuninghamhelpdesk
FRESHSERVICE_PORTAL_DOMAIN=helpdesk.cuningham.com
FRESHSERVICE_API_KEY=your-api-key-here
REQUEST_TIMEOUT_SECONDS=30
RATE_LIMIT_SLEEP_SECONDS=0.1
FRESHSERVICE_TICKET_URL_TEMPLATE=https://{domain}/a/tickets/{ticket_id}
```

#### OpenAI Configuration
```env
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_GUIDANCE_MODEL=gpt-4o-mini
OPENAI_SUMMARIZER_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini
```

#### ChromaDB Configuration
```env
CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=FreshService
```

#### Search Configuration
```env
SEARCH_MAX_DISTANCE=0.9
SEARCH_MAX_DISPLAY=5
```

#### Ingest Configuration
```env
INGEST_STATUS_CODE=5
INGEST_MAX_TOKENS=3000
INCLUDE_CONVERSATIONS_IN_EMBED=0
ENABLE_DESCRIPTION_CLEANING=1
```

#### Telemetry Configuration
```env
CHROMA_TELEMETRY_IMPLEMENTATION=disabled
```

## AI Enhancement API

### AI Summarization

The system includes AI-powered summarization for improved semantic matching between new tickets and historical closed tickets.

#### AI Summarizer Module (`ai_summarizer.py`)

**Functions:**
- `create_ticket_summary(subject, description, ticket_id=None)`: Creates AI summary
- `enhance_search_query_with_ai(query_text, ticket_id=None)`: Enhances search queries
- `create_comprehensive_ticket_embedding_text(subject, description, ticket_id=None)`: Combines AI summary with original text

**Example Usage:**
```python
from ai_summarizer import create_ticket_summary

summary = create_ticket_summary(
    "Revit desktop connector is acting up",
    "I can't open my desktop connector for some reason...",
    6511
)
# Returns: "[Ticket 6511] Issue with Revit desktop connector preventing access, impacting task completion. Symptoms include inability to open connector."
```

#### AI Enhancement Benefits
- **Improved Results**: +11% more comprehensive search results
- **Better Relevance**: AI expands technical terms and focuses on core issues
- **Semantic Matching**: Enhanced bridges between new and historical tickets
- **Fallback Safety**: Graceful degradation to raw text if AI fails

#### Configuration
AI summarization is enabled by default and can be controlled via:
- CLI: `--no-ai-summary` flag
- Streamlit: "🤖 AI-enhanced search" checkbox
- Environment: Automatic fallback if OpenAI API fails

## AI Guidance API

The AI Guidance feature provides intelligent recommendations for ticket handling by analyzing similar historical tickets and external knowledge sources.

### AI Guidance Module (`ai_recommendations.py`)

#### Core Function
- `generate_guidance(current_ticket, similar_contexts, categories_tree, detected_tokens, model, temperature)`: Generates AI-powered guidance for ticket resolution

#### Key Features

**Comprehensive Note Analysis:**
- Analyzes **ALL notes** from similar tickets (both private agent notes and public conversations)
- Prioritizes private notes that typically contain resolution details
- Handles tickets with incomplete or missing documentation gracefully
- Works effectively even when agents haven't documented perfectly

**External Knowledge Integration:**
- References external knowledge bases when applicable (Microsoft Knowledge Base, vendor documentation)
- Prioritizes company-specific knowledge bases for company-specific issues
- Includes links to external sources when available
- Only references external sources when relevant to the issue
- Can acknowledge when no helpful information is found (doesn't guess)

**Solution Variance Intelligence:**
- Recognizes that similar tickets may have different solutions
- Explains why solutions differ (environment, user skill, unique circumstances)
- Can reference multiple approaches: "Ticket X used solution A, Ticket Y used solution B"
- Identifies the most similar ticket when solutions conflict
- Considers current ticket context when comparing to similar tickets

**Information Gathering:**
- Suggests questions to ask based on missing information
- Compares commonly documented information in similar tickets vs. current ticket
- Accounts for information available via GoTo Resolve (doesn't ask for computer name, RAM, etc.)
- Flags missing context that could lead to incorrect solutions
- Questions focus on information needed to solve the issue

**Output Format:**
- Concise, structured, and scannable for busy technicians
- Avoids unnecessary fluff or lengthy explanations
- Organized for quick action-taking
- Markdown formatted for readability
- Uses headings such as Recommended Actions, Evidence, Questions, Risks, Sources

#### Return Format
```python
@dataclass
class AIGuidance:
    agent_markdown: str              # Formatted guidance for the agent
    recommended_category: List[str]  # Recommended category path
    recommended_group: str           # Suggested assignment group
    confidence: str                  # Confidence level (low/medium/high)
    supporting_tickets: List[dict]   # List of supporting ticket IDs with rationale
```

#### Example Usage
```python
from ai_recommendations import generate_guidance, AIGuidance
from config import MAX_SIMILAR_TICKETS
from search_context import gather_ticket_contexts, load_category_tree

# Gather contexts from similar tickets
similar_contexts = gather_ticket_contexts(search_results, limit=MAX_SIMILAR_TICKETS)

# Load category taxonomy
categories_tree = load_category_tree()

# Current ticket details
current_ticket = {
    "subject": "Teams video call not working",
    "description": "User reports Teams calls fail immediately...",
    "ticket_id": 6511
}

# Generate guidance
guidance = generate_guidance(
    current_ticket=current_ticket,
    similar_contexts=similar_contexts,
    categories_tree=categories_tree,
    detected_tokens=["Teams", "video", "call"],
    model="gpt-4o-mini",
    temperature=0.2
)

# Access guidance components
print(guidance.agent_markdown)           # Agent instructions
print(guidance.recommended_category)     # ['Microsoft Office 365', 'Teams']
print(guidance.recommended_group)        # 'Desktop Services'
print(guidance.confidence)               # 'high'
print(guidance.supporting_tickets)       # [{'ticket_id': 4295, 'rationale': '...'}]
```

#### Prompt Engineering

The guidance generation uses sophisticated prompts in `improved_ai_prompt.py`:

- `create_guidance_system_message()`: Defines the AI's role as an experienced IT service desk agent
- `create_ai_guidance_prompt_with_sources()`: Constructs the user prompt with:
  - Current ticket details
  - Similar tickets with ALL their notes (including privacy flags and timestamps)
  - An enforced cap via `MAX_SIMILAR_TICKETS` to control token usage
  - Category taxonomy
  - Detected tokens (software/products)
  - Assignment groups

Configuration:
- `MAX_SIMILAR_TICKETS` (env): hard cap on similar ticket contexts passed to AI guidance.

#### Configuration
- **Model**: Controlled by `OPENAI_GUIDANCE_MODEL` (default: `gpt-4o-mini`)
- **Temperature**: Default 0.2 for consistent, focused responses
- **Prompt Logging**: Set `LOG_GUIDANCE_PROMPT=1` to log full prompts for debugging

#### Error Handling
- Gracefully handles missing API keys
- Falls back to raw text if JSON parsing fails
- Logs errors without crashing the application
- Returns partial guidance when some processing fails

## Search API

### CLI Search Interface

#### Command Structure
```bash
python search_tickets.py [query] [options]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No* | - | Free text search query |
| `--seed-ticket` | int | No* | - | Ticket ID to use as search seed |
| `--max-distance` | float | No | 0.9 | Similarity threshold (0.0-2.0) |
| `--no-clean-seed` | flag | No | False | Use raw description for seed ticket |
| `--no-ai-summary` | flag | No | False | Disable AI summarization for ticket seeding |
| `--open` | int | No | - | Open Nth result in browser |

*Either `query` or `--seed-ticket` is required.

#### Examples

**Free Text Search:**
```bash
python search_tickets.py "Revit crashes and freezes"
python search_tickets.py "Teams video call problems" --max-distance 0.8
```

**Ticket Seed Search (AI-Enhanced by Default):**
```bash
python search_tickets.py --seed-ticket 4295
python search_tickets.py --seed-ticket 4295 --max-distance 0.9
python search_tickets.py --seed-ticket 4295 --no-ai-summary  # Raw text
python search_tickets.py --seed-ticket 4295 --no-clean-seed
```

**Open Results:**
```bash
python search_tickets.py "Teams issues" --open 1
python search_tickets.py --seed-ticket 4295 --open 3
```

### Programmatic Search API

#### Core Search Function
```python
from search_tickets import retrieve_similar_tickets

# Free text search
results = retrieve_similar_tickets(
    query="Teams video call problems",
    max_distance=0.8,
    n_results=20
)

# Ticket seed search
results = retrieve_similar_tickets(
    seed_ticket=4295,
    max_distance=0.55,
    n_results=10
)
```

#### Return Format
```python
[
    {
        "ticket_id": "4295",
        "subject": "Enscape Request",
        "distance": 0.0000,
        "metadata": {
            "responder_name": "Timothy Dupraz",
            "group_name": "Desktop Services",
            "category": "Software/Applications",
            "subcategory": "Enscape",
            "item": "Access",
            "priority": 2,
            "status": 5,
            "created_at": "2024-01-15T10:30:00Z"
        }
    }
]
```

## Data Ingestion API

### Ingest Command
```bash
python freshservice.py [options]
```

#### Ingest Options
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--force` | flag | False | Force re-ingestion of existing tickets |
| `--limit` | int | None | Limit number of tickets to process |
| `--start-id` | int | 1 | Starting ticket ID |
| `--end-id` | int | None | Ending ticket ID |

#### Ingest Process
1. **Data Fetching**: Retrieves tickets from Freshservice API
2. **Filtering**: Applies status and type filters
3. **Text Processing**: Cleans descriptions and removes signatures
4. **Embedding**: Generates vector embeddings using OpenAI
5. **Storage**: Stores in ChromaDB with metadata

#### Ingest Statistics
```python
{
    "total_processed": 5968,
    "successfully_embedded": 3657,
    "duplicates_skipped": 3657,
    "filtered_status": 87,
    "filtered_type": 2221
}
```

## Vision Helper API

### Extract Error Messages
```bash
python extract_error_messages.py --ticket TICKET_ID [options]
```

#### Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--ticket` | int | Yes | - | Ticket ID to process |
| `--save` | flag | No | False | Save processed images |
| `--model` | string | No | gpt-4o-mini | Vision model to use |
| `--output-dir` | string | No | ./ticket_images | Output directory |

#### Supported Image Sources
- Ticket attachments
- Conversation attachments  
- Inline images (`<img>` tags)
- Data URIs (`data:image/...`)
- Content IDs (`cid:...`)

#### Return Format
```python
{
    "ticket_id": 4295,
    "images_processed": 3,
    "error_messages": [
        "Application Error: 0x80004005",
        "Failed to initialize graphics driver"
    ],
    "saved_images": ["error1.jpg", "error2.jpg"]
}
```

## Web Interface API

### Streamlit App
```bash
streamlit run app.py --server.port 8501
```

#### Interface Components
- **Search Input**: Free text or ticket ID input
- **Distance Slider**: Adjustable similarity threshold
- **Result Display**: Categorized results with metadata
- **Filter Options**: Description view toggle, result bucketing

#### URL Parameters
- `query`: Pre-populate search query
- `ticket`: Pre-populate ticket ID
- `distance`: Set distance threshold

## Database Schema

### ChromaDB Collection Structure
```python
{
    "ids": ["11", "12", "13", ...],
    "documents": ["subject + cleaned_description", ...],
    "metadatas": [
        {
            "ticket_id": "11",
            "subject": "VTT - WUFI Add-in",
            "responder_name": "Unknown",
            "group_name": "Desktop Services",
            "category": "Software/Applications",
            "subcategory": "WUFI",
            "item": "Other - Not Listed",
            "priority": 2,
            "status": 5,
            "type": "incident",
            "created_at": "2024-01-15T10:30:00Z"
        }
    ],
    "embeddings": [[0.1, 0.2, ...], ...]
}
```

### Metadata Fields
| Field | Type | Description |
|-------|------|-------------|
| `ticket_id` | string | Freshservice ticket ID |
| `subject` | string | Ticket subject line |
| `responder_name` | string | Assigned agent name |
| `group_name` | string | Assigned group name |
| `category` | string | Primary category |
| `subcategory` | string | Secondary category |
| `item` | string | Tertiary category |
| `priority` | int | Ticket priority (1-4) |
| `status` | int | Ticket status (5=Closed) |
| `type` | string | Ticket type (incident) |
| `created_at` | string | ISO timestamp |

## Error Handling

### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (ticket doesn't exist)
- `429`: Rate Limited (API quota exceeded)
- `500`: Internal Server Error

### Error Response Format
```python
{
    "error": "ERROR_TYPE",
    "message": "Human readable error message",
    "details": {
        "ticket_id": "4295",
        "api_response": "Original API error"
    }
}
```

### Common Errors
- **Ticket Not Found**: 404 when ticket ID doesn't exist
- **API Key Invalid**: 401 when credentials are wrong
- **Rate Limited**: 429 when API limits exceeded
- **Empty Query**: Handled gracefully with fallback queries
- **ChromaDB Error**: Database connection or query issues

## Performance Metrics

### Search Performance
- **Average Query Time**: <1 second
- **Database Size**: 93MB (3,660 tickets)
- **Memory Usage**: ~200MB during operation
- **Concurrent Users**: Supports multiple simultaneous searches

### API Limits
- **Freshservice**: 100 requests/minute
- **OpenAI**: 3,000 requests/minute (tier dependent)
- **ChromaDB**: No practical limits for current dataset size

## Integration Examples

### Python Integration
```python
import sys
sys.path.append('/path/to/FreshService')

from search_tickets import retrieve_similar_tickets
from config import freshservice_session

# Search for similar tickets
results = retrieve_similar_tickets(
    query="Teams video call problems",
    max_distance=0.8
)

# Get ticket details
session = freshservice_session()
response = session.get(f"/api/v2/tickets/{results[0]['ticket_id']}")
ticket_details = response.json()
```

### Webhook Integration
```python
# Example webhook handler
def handle_new_ticket(ticket_data):
    # Search for similar historical tickets
    similar = retrieve_similar_tickets(
        query=ticket_data['subject'],
        max_distance=0.6
    )
    
    # Auto-suggest solutions or assign to appropriate agent
    if similar:
        suggest_solution(similar[0])
```

## Security Considerations

### API Key Management
- Store keys in `api.env` (not committed to version control)
- Rotate keys regularly
- Use least-privilege access

### Data Privacy
- Only closed incidents are indexed
- No PII in search results
- Text cleaning removes sensitive information

### Rate Limiting
- Built-in delays between API calls
- Configurable timeout settings
- Graceful handling of rate limit errors

---

**Last Updated**: January 2025  
**Version**: 1.0.0
