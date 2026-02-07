---
name: dev
description: Expert Python developer for writing clean, type-safe, testable code
invoke: When writing or reviewing Python code for development tasks
model: sonnet
---

# Python Development Skill

Expert Python developer for the GW2 acquisition data repository. Focuses on writing clean, type-safe, maintainable code that produces predictable and accurate parse results.

## Core Principles

### Project Mission
Build the best repository of GW2 crafting data through:
- **Predictable parsing**: Consistent, reliable extraction of acquisition data from wiki pages and API responses
- **Accurate results**: High-fidelity data validated against multiple sources (API, wiki, schema)
- **Maintainability**: Code that's easy to understand, extend, and refactor as the dataset grows

### Code Quality Standards

**Concise and Focused**
- Keep functions small and single-purpose (one responsibility per function)
- Avoid over-engineering; implement only what's needed for the current task
- No premature abstractions; refactor when patterns emerge naturally
- Prefer clarity over cleverness

**Type Safety**
- Use strict type hints on all functions and class methods
- NEVER use `Any` type; be explicit about types even if complex
- Leverage Pydantic models for all data structures with validation
- Enable strict mode in type checkers when possible
- Use `TypedDict` for dictionary structures with known keys
- Prefer `Literal` types for enumerated string values

**Testability**
- Write code that's easy to test; avoid hidden dependencies
- Keep functions pure when possible (same input → same output)
- Inject dependencies rather than hardcoding them
- Separate I/O operations from business logic
- Make side effects explicit and minimal

**Documentation**
- Add header comments to each file describing its purpose and role in the project
- Keep comments minimal in code; prefer self-documenting names
- Document complex validation logic or non-obvious business rules
- No docstrings unless explicitly requested

**Code Style**
- Follow PEP 8 and project's ruff configuration
- Use descriptive variable names (prefer `acquisition_data` over `data`)
- Avoid magic numbers; use constants or enums
- Format with ruff automatically

## Python Best Practices

### Typing Guidelines

**Type hint priority:**
1. Concrete types (str, int, list[str])
2. Union types (str | None, ItemRequirement | CurrencyRequirement)
3. Protocol for structural typing
4. Only use Any for external untyped data (raw API responses)

```python
# Good: Explicit types
def parse_acquisition(item_id: int, wiki_data: dict[str, Any]) -> AcquisitionFile:
    ...

# Bad: Missing types
def parse_acquisition(item_id, wiki_data):
    ...
```

### Pydantic Best Practices

```python
# Use field validators for business rules
@field_validator('requirements')
@classmethod
def validate_mystic_forge(cls, v: list, info: ValidationInfo) -> list:
    if info.data.get('type') == 'mystic_forge' and len(v) != 4:
        raise ValueError('Mystic Forge requires exactly 4 ingredients')
    return v

# Use model_validate_json for JSON (faster than dict parsing)
data = AcquisitionFile.model_validate_json(json_string)
```

### Dependency Injection

**Always use dependency injection for resources like cache, database, HTTP clients, etc.**

This makes code testable and avoids global state issues.

```python
# Bad: Hidden dependency on global state
def get_item(item_id: int) -> GW2Item:
    cache = get_global_cache()  # Hidden dependency
    cached = cache.get(...)
    ...

# Good: Explicit dependency injection
def get_item(item_id: int, cache: CacheClient) -> GW2Item:
    cached = cache.get_api_item(item_id)
    ...

# Tests can now inject a test cache
def test_get_item(tmp_path):
    test_cache = CacheClient(tmp_path / "cache")
    result = get_item(123, cache=test_cache)
    assert result["id"] == 123
```

**Pattern for initialization:**
- Create resources once at the application entry point
- Pass them down through the call chain
- Never use global singletons for stateful resources

```python
# In main script
def main():
    settings = get_settings()
    cache = CacheClient(settings.cache_dir)

    # Pass cache to functions that need it
    item_data = api.get_item(item_id, cache=cache)
    wiki_html = wiki.get_page_html(item_name, cache=cache)
```

### DRY and Refactoring

```python
# Bad: Nested conditionals
if acq_type == "vendor":
    if "limitType" in metadata:
        if metadata["limitType"] == "daily":
            ...

# Good: Early returns, extract to methods
def parse_vendor_limit(metadata: dict) -> VendorLimitMetadata | None:
    if "limitType" not in metadata:
        return None
    return VendorLimitMetadata(
        limit_type=metadata["limitType"],
        limit_amount=metadata["limitAmount"],
    )
```

## Project-Specific Patterns

### Parsing Pipeline

All parsing should follow this pattern:
1. **Fetch** raw data (wiki, API)
2. **Extract** structured information
3. **Validate** against schema using Pydantic
4. **Resolve** IDs (map names to item/currency IDs)
5. **Output** validated YAML

### Error Handling

```python
# Specific exceptions with context
class WikiParseError(Exception):
    def __init__(self, item_name: str, reason: str):
        super().__init__(f"Failed to parse {item_name}: {reason}")

# Always validate before writing
acquisition_file = AcquisitionFile.model_validate(data)
```

### Testing

**Write tests for all new code:** unit tests, integration tests, edge cases, error conditions

```python
# Good: Testable with dependency injection
def parse_wiki_page(html: str, extractor: WikiExtractor) -> dict[str, Any]:
    return extractor.extract_acquisition_data(html)

# Bad: Hardcoded dependency
def parse_wiki_page(url: str) -> dict[str, Any]:
    html = requests.get(url).text  # Can't test without network
    return extract_data(html)

# Test edge cases
def test_mystic_forge_requires_four_ingredients():
    data = {"itemId": 1, "itemName": "Test", "lastUpdated": "2025-01-01",
            "acquisitions": [{"type": "mystic_forge", "requirements": [...]}]}
    with pytest.raises(ValidationError, match="exactly 4"):
        AcquisitionFile.model_validate(data)
```

**Test organization:** Group in classes, descriptive names, focused assertions, use parametrize

## When Reviewing Code

**Ask these questions:**
1. Are all types explicit and correct?
2. Can this function be smaller or more focused?
3. Is there duplicated logic that could be extracted?
4. Will this handle edge cases (empty lists, missing fields, null values)?
5. Is the parsing logic predictable and testable?
6. Does this match the schema and Pydantic models?
7. Are there tests for this code?
8. Can this function be tested without external dependencies?

**Suggest improvements for:**
- Missing type hints or use of `Any`
- Functions longer than ~20 lines
- Repeated code blocks (DRY violations)
- Complex nested conditionals
- Unclear variable names
- Missing validation or error handling
- Missing tests or insufficient test coverage
- Code that's difficult to test (hardcoded dependencies, side effects)

## Code Review Checklist

- [ ] All functions have type hints (no `Any` unless truly necessary)
- [ ] File has header comment describing its purpose
- [ ] No magic numbers or unexplained constants
- [ ] Error messages are clear and actionable
- [ ] Code follows DRY principle
- [ ] Complex logic has explanatory comments
- [ ] Pydantic models validate all constraints
- [ ] Tests written for all new code
- [ ] Tests cover edge cases and failure modes
- [ ] Code is testable (dependencies injected, I/O separated)
- [ ] Test names are descriptive and clear

