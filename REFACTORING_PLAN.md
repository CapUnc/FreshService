# 🔧 Refactoring Plan for Efficiency Improvements

## Executive Summary
This document outlines efficiency improvements and refactoring opportunities identified in the FreshService codebase. The analysis focuses on code duplication, API call optimization, caching strategies, and resource reuse.

---

## 🔴 High Priority Refactoring

### 1. Consolidate HTML Parsing Functions
**Issue:** `_html_to_text()` is duplicated in 3 files:
- `freshservice.py` (line 36)
- `search_tickets.py` (line 43)  
- `search_context.py` has `_clean_text()` (line 230) which does similar HTML parsing

**Impact:** Code duplication, maintenance burden, potential inconsistencies

**Solution:**
- Create a shared utility module `utils.py` or add to `text_cleaning.py`
- Consolidate all HTML-to-text parsing into one function
- Update all imports

**Files to modify:**
- Create/update `text_cleaning.py` with `html_to_text()` function
- Update `freshservice.py`, `search_tickets.py`, `search_context.py`

**Estimated effort:** 30 minutes

---

### 2. Unify Agent/Group Name Lookup with Consistent Caching
**Issue:** Three different implementations of agent/group name resolution:
- `freshservice.py`: `_get_agent_name()`, `_get_group_name()` with module-level dict cache
- `search_tickets.py`: `_fetch_agent_name()` with `@lru_cache(maxsize=4096)`
- `search_context.py`: `_resolve_group_name()` with module-level dict cache

**Impact:** 
- Inconsistent caching strategies
- Potential duplicate API calls
- Code duplication
- Different error handling patterns

**Solution:**
- Create unified `agent_resolver.py` module with:
  - `get_agent_name(agent_id: int) -> str` with `@lru_cache`
  - `get_group_name(group_id: int) -> str` with `@lru_cache`
  - Shared session reuse
  - Consistent retry logic
- Replace all three implementations

**Files to modify:**
- Create `agent_resolver.py`
- Update `freshservice.py`, `search_tickets.py`, `search_context.py`
- Remove duplicate code

**Estimated effort:** 1-2 hours

---

### 3. Reuse HTTP Sessions
**Issue:** `freshservice_session()` is called multiple times, creating new sessions:
- `app.py`: 2 calls (lines 258, 831)
- `search_context.py`: 1 call (line 74)
- `search_tickets.py`: 3 calls (lines 57, 236, 257)
- `freshservice.py`: 1 call (line 238)

**Impact:** 
- Unnecessary connection overhead
- Missing HTTP connection pooling benefits
- Potential rate limiting issues

**Solution:**
- Pass session as parameter to functions that need it
- Create session once at module/function scope and reuse
- For Streamlit app, use `@st.cache_resource` to cache session

**Files to modify:**
- `app.py`: Cache session with `@st.cache_resource`
- `search_context.py`: Accept session parameter
- `search_tickets.py`: Accept session parameter where possible
- `freshservice.py`: Create session once in `main()`

**Estimated effort:** 1 hour

---

## 🟡 Medium Priority Refactoring

### 4. Batch API Calls for Ticket Contexts
**Issue:** `gather_ticket_contexts()` makes sequential API calls (line 92 in search_context.py):
```python
for doc, meta, dist in results:
    ticket_ctx = _fetch_ticket_context(session, int(ticket_id), dist)
```

**Impact:**
- Slow when fetching multiple ticket contexts
- Sequential blocking calls
- No parallelization

**Solution:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel API calls
- Limit concurrency to respect rate limits (e.g., max_workers=5)
- Maintain order of results

**Files to modify:**
- `search_context.py`: Update `gather_ticket_contexts()`

**Estimated effort:** 1 hour

---

### 5. Consolidate BeautifulSoup Usage
**Issue:** BeautifulSoup is imported and used in multiple places:
- `search_context.py`: `_clean_text()` (line 233)
- `search_tickets.py`: `_html_to_text()` (line 46)
- `freshservice.py`: `_html_to_text()` (line 39)

**Impact:**
- Multiple parser instantiations
- Inconsistent parsing behavior

**Solution:**
- Use consolidated HTML parsing from #1
- Consider caching BeautifulSoup parser instance if performance is critical

**Files to modify:**
- Same as #1

**Estimated effort:** Included in #1

---

### 6. Optimize Category Tree Loading
**Issue:** `load_category_tree()` in `search_context.py` (line 50) reads file every time:
- No caching
- File I/O on every call

**Solution:**
- Add `@lru_cache` decorator
- Or cache at module level with file modification time check

**Files to modify:**
- `search_context.py`: Add caching to `load_category_tree()`

**Estimated effort:** 15 minutes

---

## 🟢 Low Priority / Nice to Have

### 7. Streamline Metadata Sanitization
**Issue:** `sanitize_metadata()` in `freshservice.py` (line 211) is called for every ticket during ingestion

**Impact:**
- Minor performance overhead
- Could be optimized for bulk operations

**Solution:**
- Consider batching metadata sanitization
- Profile to see if this is actually a bottleneck

**Estimated effort:** 30 minutes (if needed)

---

### 8. Cache Known Tokens More Efficiently
**Issue:** `_load_known_tokens()` in `search_intent.py` uses `@lru_cache(maxsize=1)` but reads file

**Current:** Already cached, but could check file modification time

**Solution:**
- Add file modification time check to invalidate cache when file changes
- Or use a more sophisticated caching strategy

**Files to modify:**
- `search_intent.py`

**Estimated effort:** 30 minutes

---

### 9. Optimize Result Processing
**Issue:** Multiple passes over results in `search_tickets.py`:
- `_resolve_agents_for_results()` (line 305)
- `_rerank_results()` (line 309)
- `_apply_strict_filters()` (line 367)

**Impact:**
- Multiple iterations over same data
- Could combine some operations

**Solution:**
- Combine operations where possible
- Use generators for large result sets
- Profile to identify actual bottlenecks

**Estimated effort:** 1 hour (if profiling shows it's needed)

---

## 📊 Performance Impact Estimates

| Refactoring | Performance Gain | Complexity | Priority |
|------------|------------------|------------|----------|
| 1. Consolidate HTML parsing | Low | Low | High (maintainability) |
| 2. Unify agent/group lookup | Medium | Medium | High |
| 3. Reuse HTTP sessions | Medium | Low | High |
| 4. Batch API calls | High | Medium | Medium |
| 5. Consolidate BeautifulSoup | Low | Low | Medium (part of #1) |
| 6. Cache category tree | Low | Low | Medium |
| 7. Streamline metadata | Low | Low | Low |
| 8. Cache known tokens | Low | Low | Low |
| 9. Optimize result processing | Low | Medium | Low |

---

## 🎯 Recommended Implementation Order

### Phase 1: Quick Wins (2-3 hours)
1. **Consolidate HTML parsing** (#1, #5)
2. **Cache category tree** (#6)
3. **Reuse HTTP sessions in app.py** (#3 - partial)

### Phase 2: Core Improvements (3-4 hours)
4. **Unify agent/group lookup** (#2)
5. **Complete session reuse** (#3)
6. **Batch API calls** (#4)

### Phase 3: Polish (if needed)
7. Profile and optimize based on actual usage patterns
8. Implement remaining low-priority items if profiling shows benefits

---

## 🔍 Code Duplication Summary

### Functions with Duplicate Logic:
1. **HTML parsing**: 3 implementations
2. **Agent name lookup**: 3 implementations  
3. **Group name lookup**: 3 implementations
4. **Session creation**: Multiple calls, could be reused

### Estimated Lines of Code to Remove:
- ~150-200 lines of duplicate code
- Potential reduction in maintenance burden

---

## ⚠️ Considerations

### Rate Limiting
- Freshservice API has rate limits (100 requests/minute mentioned in docs)
- Batch operations (#4) must respect these limits
- Use appropriate delays and concurrency limits

### Caching Strategy
- `@lru_cache` vs module-level dicts: `@lru_cache` is more memory-efficient and thread-safe
- Consider cache size limits to prevent memory issues
- May need cache invalidation strategies for long-running processes

### Backward Compatibility
- Ensure refactoring doesn't break existing functionality
- Test all code paths that use refactored functions
- Update imports across all files

### Testing
- Add unit tests for new consolidated functions
- Test caching behavior
- Test session reuse
- Test parallel API calls with rate limiting

---

## 📝 Implementation Notes

### For HTML Parsing Consolidation:
```python
# text_cleaning.py
def html_to_text(html: Optional[str]) -> str:
    """Convert HTML to plain text, handling None/empty input."""
    if not html:
        return ""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
```

### For Agent/Group Resolver:
```python
# agent_resolver.py
from functools import lru_cache
from config import freshservice_session, FRESHSERVICE_BASE_URL, REQUEST_TIMEOUT, RATE_LIMIT_SLEEP

@lru_cache(maxsize=8192)
def get_agent_name(agent_id: int) -> str:
    """Get agent name with caching and retry logic."""
    # Unified implementation
    pass

@lru_cache(maxsize=4096)
def get_group_name(group_id: int) -> str:
    """Get group name with caching and retry logic."""
    # Unified implementation
    pass
```

### For Session Reuse in Streamlit:
```python
# app.py
@st.cache_resource
def get_freshservice_session():
    return freshservice_session()
```

---

**Generated:** 2025-01-21  
**Status:** Ready for Implementation
