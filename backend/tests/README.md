# FinSight Test Suite

## Running Tests

```powershell
cd backend
py -m pytest tests/ -v
```

Run specific test files:
```powershell
py -m pytest tests/test_services/ -v
py -m pytest tests/test_routers/ -v
py -m pytest tests/test_integration/ -v
```

Run with coverage:
```powershell
py -m pytest tests/ --cov=app --cov-report=term-missing
```

## Test Coverage

### What Tests Cover

| Component | Tests | Status |
|-----------|-------|--------|
| JellyfinClient | 8 tests | Full coverage |
| NewsletterGenerator | 3 tests | Full coverage |
| LibraryJanitor (count/stats) | 2 tests | Partial |
| API Integration | 7 tests | Most endpoints |
| Router endpoints | Varies | Some coverage |

### Test Types

1. **Service Unit Tests** (`test_services/`)
   - Mock-based testing of business logic
   - No real database or network calls

2. **Router Tests** (`test_routers/`)
   - HTTP endpoint testing with test client
   - Use in-memory SQLite for database

3. **Integration Tests** (`test_integration/`)
   - Full application flow testing
   - Seeded test data for realistic scenarios

### Passing Tests (50 — up from 30 in v0.x)

- All JellyfinClient service methods (8 tests)
- NewsletterGenerator (get_week_range, render_html) (3 tests)
- LibraryJanitor (get_cold_media, get_cold_count, get_user_stats) (5 tests)
- Integration API endpoints (7 tests)
- Janitor router (cold media, CSV export, user stats, metrics) (6 tests)
- Media router (media detail, library stats) (4 tests)
- Newsletter router (preview, generate, latest) (5 tests)
- Sessions router (active, history, stats, idle exclusion, stale media) (10 tests) — 3 new in v1.0

## What Tests DON'T Cover

### Not Tested

- **Watchdog service** - Background polling logic, session state machine
- **Webhook processing** - Model exists but no consumer logic
- **Media file size polling** - MediaSources field not tested
- **User authentication** - No auth system (by design)
- **Full database CRUD** - Only specific queries tested

### Known Limitations

- Router tests have async dependency injection complexity
- Some endpoints require more complex fixture setup
- Transcode ratio edge cases (division by zero prevention)
- Timezone handling in date comparisons

### Manual Testing Recommended

1. Full Jellyfin API integration (validation, sessions, users)
2. Watchdog polling loop behavior
3. Newsletter generation with real data
4. Library janitor cold media calculation accuracy
5. Real-time active session tracking
6. Demo mode seed script correctness

## Adding Tests

1. Add test file to appropriate folder
2. Use `conftest.py` fixtures for database/sessions
3. Mark async tests with `@pytest.mark.asyncio`
4. Use `enable_demo_mode` fixture to skip Jellyfin connection
5. Use `test_engine` fixture for in-memory SQLite

### Example Test

```python
@pytest.mark.asyncio
async def test_example(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        response = c.get("/api/health")
        assert response.status_code == 200

    app.dependency_overrides.clear()
```

## Dependencies

Tests require:
- pytest
- pytest-asyncio
- pytest-mock

Install via:
```powershell
pip install pytest pytest-asyncio pytest-mock
```