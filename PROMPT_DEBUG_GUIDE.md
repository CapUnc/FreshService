# AI Guidance Prompt Debugging Guide

## What Was Added

Added debug logging to `ai_recommendations.py` lines 109-114:

```python
# Debug logging for prompt verification
if os.getenv("LOG_GUIDANCE_PROMPT") == "1":
    logger.info("=== OpenAI guidance request ===")
    logger.info("System: %s", system_prompt)
    logger.info("User: %s", user_instruction)
    logger.info("Payload: %s", json.dumps(prompt_payload, ensure_ascii=False))
```

## How to Test

### Method 1: Use the Setup Script
```bash
./setup_prompt_debug.sh
```

### Method 2: Manual Steps
1. **Start Streamlit with debug logging:**
   ```bash
   LOG_GUIDANCE_PROMPT=1 streamlit run app.py
   ```

2. **Watch the debug log in another terminal:**
   ```bash
   tail -f freshservice_debug.log
   ```

3. **In the Streamlit app:**
   - Clear any cached AI guidance: `st.session_state["ai_guidance"] = None`
   - Or restart the app completely
   - Click "✨ Generate AI Guidance" button
   - Check the log output

## What You'll See in the Log

```
=== OpenAI guidance request ===
System: You are an experienced IT service desk agent. Using the current Freshservice ticket details alongside how similar historical tickets were handled (including work notes) and the category taxonomy, recommend actionable next steps for the assigned agent.
User: Using the JSON payload below--which pairs the ticket we are working on with knowledge of how similar tickets were handled--recommend next actions for the agent...
Payload: {"current_ticket": {...}, "similar_tickets": [...], ...}
```

## Important Notes

- **Restart Required**: Streamlit keeps state, so restart the app or clear `st.session_state["ai_guidance"]`
- **Security**: The debug log contains sensitive ticket data - remove the env var when done testing
- **Log Location**: Output goes to `freshservice_debug.log` and stdout if running locally

## Current Prompt Text

The prompts should now show:
- **System**: "Using the current Freshservice ticket details alongside how similar historical tickets were handled..."
- **User**: "Using the JSON payload below--which pairs the ticket we are working on with knowledge of how similar tickets were handled..."

If you see different text, the running process hasn't picked up the code changes yet - restart the app.

