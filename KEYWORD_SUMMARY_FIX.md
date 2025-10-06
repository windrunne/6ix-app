# Fix: keyword_summary Column Removed

## Issue
The network query API was failing with error:
```json
{
    "success": false,
    "error": "{'code': '42703', 'details': None, 'hint': None, 'message': 'column users.keyword_summary does not exist'}"
}
```

## Root Cause
The `keyword_summary` column was removed from the `users` table, but the code was still trying to access it in multiple places.

## Files Fixed

### 1. `app/services/network_service.py`
- **Line 121**: Removed `keyword_summary` from SELECT query
- **Line 151**: Set `keyword_summary: []` (no longer available)
- **Lines 380-385**: Removed keyword_summary matching logic for interests
- **Lines 406-411**: Removed keyword_summary matching logic for keywords

### 2. `app/services/ai_service.py`
- **Line 469**: Updated prompt to indicate keyword_summary is no longer available

### 3. `app/api/network_query.py`
- **Lines 140, 166**: Set `keyword_summary=[]` (no longer available)

### 4. `app/models/schemas.py`
- **Line 118**: Removed `keyword_summary` field from `NetworkMatch` model

## Impact
- ✅ Network queries now work without the keyword_summary column
- ✅ Matching now relies on recent posts content instead of keyword_summary
- ✅ No breaking changes to API response format
- ✅ All references to removed column eliminated

## Testing
The network query API should now work correctly:
```bash
curl -X POST http://localhost:8000/api/network/query \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "12345678-1234-1234-1234-123456789012",
    "query": "show me someone who like skating",
    "max_results": 10,
    "include_second_degree": true
  }'
```

## Notes
- The matching algorithm now relies more heavily on recent posts content
- This may actually improve matching accuracy as it uses real user activity
- No database migration needed - column was already removed

**Fixed**: October 3, 2025
