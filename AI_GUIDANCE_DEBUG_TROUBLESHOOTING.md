# AI Guidance Debug Troubleshooting Guide

## The Issue
You're not seeing debug logs after clicking the AI guidance button. Here's how to troubleshoot:

## Step 1: Verify Environment Variable
The debug logging only works when `LOG_GUIDANCE_PROMPT=1` is set.

**Test this:**
```bash
# Check if variable is set
echo $LOG_GUIDANCE_PROMPT

# Should output: 1
# If it outputs nothing, the variable isn't set
```

## Step 2: Start Streamlit with Debug Logging
```bash
# Method 1: Use the test script
./test_ai_guidance_debug.sh

# Method 2: Manual
LOG_GUIDANCE_PROMPT=1 streamlit run app.py
```

## Step 3: Clear Streamlit Cache
Streamlit caches AI guidance results. You need to clear the cache:

**In the Streamlit app:**
1. Look for the "Clear Cache" button in the sidebar
2. Or restart the app completely
3. Or clear `st.session_state["ai_guidance"]` programmatically

## Step 4: Test the AI Guidance Button
1. Enter a ticket ID (like 6498) or search text
2. Wait for search results to appear
3. Click "✨ Generate Guidance" button
4. Watch the terminal for debug output

## Step 5: Check for Errors
If the AI guidance fails, you'll see an error message in the Streamlit app:
```
Failed to generate guidance: [error message]
```

Common errors:
- Missing OpenAI API key
- Network issues
- Invalid ticket data

## Step 6: Verify Debug Output
You should see output like this in the terminal:
```
=== OpenAI guidance request ===
System: You are an experienced IT service desk agent. Using the current Freshservice ticket details alongside how similar historical tickets were handled...
User: Using the JSON payload below--which pairs the ticket we are working on with knowledge of how similar tickets were handled...
Payload: {"current_ticket": {...}, "similar_tickets": [...], ...}
```

## Troubleshooting Checklist

- [ ] Environment variable `LOG_GUIDANCE_PROMPT=1` is set
- [ ] Streamlit was started with the environment variable
- [ ] Streamlit cache has been cleared
- [ ] Search results are visible before clicking AI guidance
- [ ] No error messages appear in the Streamlit app
- [ ] Terminal shows debug output when button is clicked

## Quick Test Commands

```bash
# Test environment variable
LOG_GUIDANCE_PROMPT=1 python3 -c "import os; print('Set:', os.getenv('LOG_GUIDANCE_PROMPT'))"

# Test logging
LOG_GUIDANCE_PROMPT=1 python3 -c "
import logging
logger = logging.getLogger('test')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('freshservice_debug.log', mode='a')
logger.addHandler(handler)
logger.info('=== TEST LOGGING ===')
print('Test complete')
"

# Check log
tail -5 freshservice_debug.log
```

