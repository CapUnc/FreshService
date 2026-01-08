# Freshservice Semantic Search v2.0 - User Guide

## Quick Start

### Smart Startup (Recommended)
```bash
# Use the intelligent startup script
python start_app.py

# Or run diagnostics only
python start_app.py --diagnostics-only
```

### Web Interface (Recommended)
1. Open your browser to: http://localhost:8501
2. Toggle "🤖 AI-enhanced search" for better results (enable via `USE_AI_SUMMARY=1`)
3. Enter your search query or ticket ID
4. Adjust the distance threshold if needed (default: 0.9)
5. Review results and click to open tickets

### Command Line (Power Users)
```bash
# Search for similar tickets (AI-enhanced when enabled)
python search_tickets.py "Teams video call problems"

# Find tickets similar to a specific ticket (AI-enhanced when enabled)
python search_tickets.py --seed-ticket 4295

# Use raw text (no AI enhancement)
python search_tickets.py --seed-ticket 4295 --no-ai-summary
```

## Data Maintenance

- Run `python freshservice.py` to ingest or refresh embeddings. The script pulls **only closed incident tickets** (status code 5) and skips service requests by design.
- Existing vectors are deduplicated by ticket ID; rerunning the script is safe and updates changed tickets.
- Schedule the ingestion command (nightly or hourly) once the app is deployed in the work environment to keep search results current.
- Use `python freshservice.py --since-days 7` (or `INGEST_SINCE_DAYS=7`) to limit ingestion to recently updated tickets.

## Understanding Search Results

### Distance Scores
The system shows how similar each result is to your query:
- **0.0000**: Exact match (perfect similarity)
- **0.0 - 0.3**: Very similar (high confidence)
- **0.3 - 0.6**: Similar (good matches)
- **0.6 - 0.8**: Related (loosely connected)
- **0.8 - 0.9**: Distant (weak connection, default threshold)
- **0.9+**: Very distant (very weak connection)

**Note**: The default threshold is now 0.9 for broader, more comprehensive results.

### Result Information
Each result shows:
- **Ticket ID**: Click to open in Freshservice
- **Subject**: The ticket title
- **Agent**: Who handled the ticket
- **Group**: Which team handled it
- **Category Path**: Full categorization
- **Distance**: Similarity score

## Strict Filtering Options

Use strict filters when you need high precision:

- **Require exact software terms**: Removes tickets that do not mention the same high-signal product keywords detected in your query. (Streamlit toggle or `--require-token` in the CLI)
- **Require same category**: With a seeded ticket, keep only results that share the same category/subcategory/item path. (Streamlit toggle or `--same-category-only` in the CLI)

When these filters eliminate all results, relax them to broaden the search again.

## AI Guidance

The **✨ Generate AI Guidance** button provides intelligent, actionable recommendations for handling tickets based on similar historical cases and external knowledge sources.

### How It Works

1. **Analysis Process**: The AI analyzes:
   - **All notes** from similar tickets (both private agent notes and public conversations)
   - The current ticket's full context (subject, description, detected software/products)
   - Patterns and solutions from historical similar tickets
   - External knowledge bases when applicable (Microsoft Knowledge Base, vendor documentation, etc.)

2. **Intelligent Recommendations**: The AI provides:
   - **Actionable next steps** tailored to the current ticket's specific context
   - **Questions to ask** when important information is missing (based on what's commonly documented in similar tickets)
   - **Recommended category path** for proper ticket classification:
     * Three-level structure: `Category → Subcategory → Item` (e.g., "Microsoft Office 365 → Teams → Crash/Error/Freeze")
     * AI is instructed to provide complete paths when items exist
     * **Automatic item inference**: If the AI provides only 2 levels, the system automatically fills in the missing item based on similar tickets or taxonomy
   - **Suggested assignment group** with confidence level
   - **External resources** with links when relevant (prioritizes company-specific knowledge bases when available)

3. **Solution Variance Understanding**: The AI recognizes that:
   - Similar tickets may have different solutions (different environments, user skill levels, unique circumstances)
   - Not all similar tickets require identical solutions
   - Context differences between tickets matter
   - It can reference multiple approaches: "One ticket used X solution, another used Y solution"

4. **Information Handling**:
   - **Missing Information**: Suggests questions to gather needed details that are commonly documented in similar tickets
   - **Available Information**: Accounts for information accessible via GoTo Resolve (computer name, RAM, etc.) and doesn't ask for what can be retrieved automatically
   - **Gaps and Risks**: Flags missing context that could lead to incorrect solutions
   - **Incomplete Documentation**: Works effectively even when similar tickets have minimal or imperfect documentation

5. **External Sources**:
   - References external knowledge bases (Microsoft KB, vendor documentation) when applicable
   - Prioritizes company-specific knowledge bases for company-specific issues
   - Includes links to sources when available
   - Only references external sources when relevant (not all tickets involve software with external documentation)
   - Can acknowledge when no helpful information is found in similar tickets or external sources (doesn't guess)

### Output Format

The guidance is formatted for **efficient consumption by busy technicians**:
- Concise, structured, and scannable
- Avoids unnecessary fluff or lengthy explanations
- Organized for quick action-taking
- Markdown formatted for readability

### When to Use

- **Before starting work on a ticket**: Get recommended approach and questions to ask
- **When stuck**: Find how similar issues were resolved
- **For routing decisions**: Get category and assignment group recommendations
- **For knowledge gaps**: Access external resources and historical solutions

### Best Practices

- Review the most similar tickets cited in the guidance
- Check if external resources are applicable to your specific environment
- Consider the suggested questions - they're based on what information is typically needed for similar issues
- Use confidence levels to gauge recommendation strength
- Generate new guidance if you've gathered additional information or filtered results differently

**Note**: Click the button again to regenerate guidance after adjusting filters or gathering more information about the ticket.

## AI Enhancement Features

### 🤖 AI-Enhanced Search
The system now includes AI-powered summarization that significantly improves search results:

#### How It Works
1. **New Ticket Input**: You provide a ticket ID or description
2. **AI Processing**: System creates an optimized summary using the model set in `OPENAI_SUMMARIZER_MODEL` (default: `gpt-4o-mini`)
3. **Enhanced Search**: Uses AI summary to find similar historical tickets
4. **Better Results**: +11% more comprehensive and relevant results

#### Benefits
- **Better Semantic Matching**: AI expands technical terms and focuses on core issues
- **Improved Relevance**: More accurate connections between new and historical tickets
- **Fallback Safety**: Automatically uses raw text if AI fails
- **Cost Controlled**: Adjust `OPENAI_SUMMARIZER_MODEL` to balance quality and token cost (`gpt-4o-mini` is the default sweet spot)

#### Control Options
- **Streamlit**: Toggle "🤖 AI-enhanced search" checkbox
- **CLI**: Use `--no-ai-summary` flag to disable
- **Default**: AI enhancement is enabled by default

#### Example
**Original Ticket**: "Revit desktop connector is acting up"
**AI Summary**: "[Ticket 6511] Issue with Revit desktop connector preventing access, impacting task completion. Symptoms include inability to open connector."
**Result**: 172 relevant tickets vs 155 with raw text (+11% improvement)

## Search Strategies

### 1. Free Text Search
Use natural language to describe the problem:

**Good Examples:**
- "Revit crashes when opening large files"
- "Teams video calls not working"
- "Email not syncing on mobile"
- "Bluebeam PDFs not opening"
- "Enscape rendering errors"

**Tips:**
- Be specific about the application or issue
- Include error messages if you know them
- Use common IT terms (crashes, freezes, errors, not working)

### 2. Ticket Seed Search
Start with a ticket ID to find similar issues:

**When to Use:**
- You have a ticket that's similar to the current issue
- You want to find patterns in related problems
- You're escalating and need historical context
- You want to see how similar issues were resolved

**How to Use:**
1. Find a relevant ticket ID in Freshservice
2. Use the seed search: `--seed-ticket 4295`
3. Review results to see related tickets
4. Look for patterns in solutions

### 3. Category-Based Search
Search within specific categories:

**Software/Applications:**
- "Revit" - Autodesk Revit issues
- "Bluebeam" - PDF markup software
- "Enscape" - Rendering software
- "SketchUp" - 3D modeling

**Microsoft Office 365:**
- "Teams" - Video conferencing
- "Outlook" - Email client
- "SharePoint" - Document sharing

**Hardware:**
- "Computer" - Desktop/laptop issues
- "Docking Station" - External hardware
- "Monitor" - Display problems

**Network:**
- "VPN" - Remote access
- "Connectivity" - Network issues
- "Remote" - Working from home

## Distance Threshold Guide

### Understanding Thresholds
The distance threshold controls how similar results must be to your query:

- **0.1 - 0.3**: Very Precise
  - Few results, very high quality
  - Use when you know exactly what you're looking for
  - Good for specific error messages

- **0.3 - 0.6**: Balanced (Recommended)
  - Good mix of precision and recall
  - Default setting for most searches
  - Catches most relevant results

- **0.6 - 0.8**: Broad Search
  - More results, includes loosely related
  - Use when you need to cast a wide net
  - Good for exploratory searches

- **0.8+**: Very Broad
  - Many results, may include tangentially related
  - Use when you're stuck and need ideas
  - Can help discover unexpected connections

### Choosing the Right Threshold

**Start with 0.55** (default) and adjust based on results:

- **Too few results?** → Increase threshold (try 0.7 or 0.8)
- **Too many irrelevant results?** → Decrease threshold (try 0.3 or 0.4)
- **Found what you need?** → Perfect! Keep that threshold

## Common Use Cases

### 1. New User Problem
**Scenario**: User reports "Teams not working"
**Search Strategy**:
1. Try: "Teams not working" (threshold: 0.6)
2. If too broad, try: "Teams video call problems" (threshold: 0.5)
3. Look for patterns in solutions

### 2. Escalation Support
**Scenario**: Ticket needs escalation, need historical context
**Search Strategy**:
1. Use the current ticket ID as seed
2. Set threshold to 0.7 for broader results
3. Review how similar issues were resolved
4. Note patterns in agent assignments and solutions

### 3. Pattern Recognition
**Scenario**: Multiple users reporting similar issues
**Search Strategy**:
1. Search with the common problem description
2. Use threshold 0.6 to catch variations
3. Look for trends in timing, users, or solutions
4. Identify if it's a systemic issue

### 4. Solution Discovery
**Scenario**: Need to find how a specific problem was solved
**Search Strategy**:
1. Search with specific error message or problem
2. Use threshold 0.4 for precise matches
3. Look for tickets marked as resolved
4. Check resolution notes and solutions

### 5. Knowledge Building
**Scenario**: Learning about common issues in your environment
**Search Strategy**:
1. Search by application name (e.g., "Revit")
2. Use threshold 0.7 to see variety of issues
3. Review top categories and common problems
4. Build understanding of typical issues and solutions

## Advanced Tips

### Query Optimization

**Be Specific:**
- ❌ "Computer broken"
- ✅ "Computer won't boot, blue screen error"

**Include Context:**
- ❌ "Email not working"
- ✅ "Outlook not syncing email on iPhone"

**Use Technical Terms:**
- ❌ "Program crashes"
- ✅ "Revit crashes when opening family files"

### Result Analysis

**Look for Patterns:**
- Which agents handle similar issues?
- What are common resolution paths?
- Are there recurring problems?

**Check Resolution Status:**
- Focus on resolved tickets for solutions
- Note resolution times and methods
- Identify successful resolution patterns

**Metadata Insights:**
- Category paths show problem classification
- Agent assignments show expertise areas
- Priority levels indicate severity patterns

### Workflow Integration

**Daily Ticket Review:**
1. Start each day with a broad search for recent issues
2. Look for patterns in overnight tickets
3. Use seed search on complex tickets

**Escalation Process:**
1. Search for similar historical issues
2. Review resolution patterns
3. Identify appropriate escalation paths

**Knowledge Management:**
1. Regularly search for common issues
2. Build internal documentation from search results
3. Share successful resolution patterns with team

## Troubleshooting

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

### Search Issues

#### No Results Found
**Possible Causes:**
- Query too specific or unusual
- Distance threshold too restrictive
- Issue might be very rare
- AI enhancement disabled when it would help

**Solutions:**
- Try broader terms
- Increase distance threshold (default is now 0.9)
- Enable AI-enhanced search for better results
- Use free text search instead of ticket seeding
- Try different wording
- Search by application name instead

### Too Many Results
**Possible Causes:**
- Query too general
- Distance threshold too broad
- Common issue with many variations

**Solutions:**
- Be more specific in query
- Decrease distance threshold
- Add more context to query
- Use category-specific terms

### Irrelevant Results
**Possible Causes:**
- Query terms have multiple meanings
- Distance threshold too broad
- Need more specific technical terms

**Solutions:**
- Use more technical language
- Decrease distance threshold
- Add application-specific terms
- Try seed search instead

### Slow Search Performance
**Possible Causes:**
- Very broad distance threshold
- Complex query processing
- High system load

**Solutions:**
- Reduce distance threshold
- Simplify query terms
- Try during off-peak hours
- Contact system administrator

### ChromaDB Telemetry Warnings
**Symptom:** Repeated log messages such as `capture() takes 1 positional argument but 3 were given` when starting the app or running ingestion.

**What it means:** The bundled PostHog client in ChromaDB 0.4.x does not match the `posthog` version installed locally. It is harmless, but noisy.

**Resolution:** Set either of the following environment variables before launching the app or ingest script:

```bash
export CHROMA_TELEMETRY_IMPLEMENTATION=disabled
# or (newer builds)
export CHROMA_TELEMETRY_ENABLED=0
```

Add the variable to your shell profile or process supervisor when moving to the work environment.

## Best Practices

### Search Etiquette
- Use clear, descriptive queries
- Start broad, then narrow down
- Don't search for personal information
- Respect system resources

### Result Usage
- Verify information before acting
- Check ticket status and resolution
- Don't assume all historical solutions are current
- Use results as guidance, not definitive answers

### Continuous Improvement
- Share successful search strategies with team
- Document effective query patterns
- Provide feedback on search quality
- Suggest improvements to the system

## Getting Help

### Self-Service
1. Try different search terms
2. Adjust distance threshold
3. Use seed search with known good tickets
4. Check this guide for examples

### Team Support
- Ask colleagues for search tips
- Share successful query patterns
- Collaborate on complex searches
- Escalate system issues to administrator

### System Issues
- Report bugs or performance problems
- Suggest new features
- Provide feedback on search quality
- Request additional training

---

**Remember**: The semantic search is a powerful tool, but it works best when combined with your domain knowledge and experience. Use it to enhance your troubleshooting process, not replace your judgment.

**Last Updated**: October 2025  
**Version**: 1.1.0
