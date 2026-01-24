"""
Coze Platform Integration Module
==================================

This module provides programmatic integration with the Coze (扣子) platform,
a Chinese AI skills marketplace, enabling Mosaic nodes to search, install,
invoke, and retrieve results from Coze skills.

## Architecture Overview

Since Coze does not provide an official API, this integration uses browser
automation via Playwright to interact with the web platform:

    Mosaic Node (Claude Code)
        ↓
    MCP Tools (claude_code.py)
        ↓
    CozeClient (client.py)
        ↓
    BrowserManager (browser.py)
        ↓
    Playwright + CDP
        ↓
    Browser Instance (Chrome with remote debugging)
        ↓
    Coze Platform (https://www.coze.cn)

## Modules

### browser.py
- **Purpose**: Manage browser connection lifecycle
- **Key Class**: `BrowserManager` (singleton)
- **Responsibilities**:
  - Connect to browser via CDP (Chrome DevTools Protocol)
  - Maintain persistent browser session
  - Handle connection pooling and reuse
  - Manage page lifecycle

### client.py
- **Purpose**: High-level Coze platform operations
- **Key Class**: `CozeClient`
- **Responsibilities**:
  - Search skills by keyword
  - Install skills
  - Invoke skills with task prompts
  - Retrieve task results
  - Handle errors and retries

## Key Technologies

- **Playwright**: Browser automation framework
- **CDP (Chrome DevTools Protocol)**: Connect to running browser
- **API Interception**: Capture network requests for data extraction
- **Async/Await**: Asynchronous I/O for browser operations

## Configuration

### Browser Setup
The browser must be running with remote debugging enabled:

```bash
chrome --remote-debugging-port=19222
```

Default CDP endpoint: `http://192.168.1.4:19222`

### Prerequisites
1. Chrome/Chromium browser installed
2. User logged into Coze platform in the browser
3. Browser running with remote debugging enabled
4. Playwright installed: `pip install playwright`

## Usage Example (Conceptual)

```python
from mosaic.v2.backend.integrations.coze import CozeClient

async def demo():
    client = CozeClient()

    # Search for skills
    skills = await client.search_skill("数据分析", max_results=5)

    # Install a skill
    await client.install_skill(skill_id=skills[0]['skill_id'])

    # Invoke the skill
    task_info = await client.invoke_skill(
        skill_id=skills[0]['skill_id'],
        prompt="分析这份销售数据"
    )

    # Get results
    result = await client.get_result(
        task_id=task_info['task_id'],
        wait=True,
        timeout=120
    )

    print(f"AI Reply: {result['reply']}")
    print(f"Files: {result['files']}")
```

## Implementation Status

⚠️ **TODO**: This module is currently a stub. Implementation is pending.

Reference implementation and documentation can be found in:
- `mosaic/experiments/coze_integration/`

## Performance Notes

- **Search**: 1-2 seconds (via API interception, 20x faster than DOM parsing)
- **Install**: 2-5 seconds (browser interaction)
- **Invoke**: 1-3 seconds (URL-based activation)
- **Get Result**: Depends on task complexity (with polling)

## Error Handling

The client should handle:
- Browser connection failures
- Login session expiration
- Network timeouts
- Skill not found errors
- Task execution failures
- API rate limiting

## Security Considerations

- Login credentials stored in browser session
- No credential handling in code
- Reuses existing authenticated browser session
- CDP connection should be restricted to localhost/trusted network

## Future Improvements

1. Support for batch operations
2. Caching of skill metadata
3. Connection pool management
4. Graceful degradation on browser failure
5. Metrics and logging
6. Official API support (if/when available)

## References

- Coze Platform: https://www.coze.cn
- Playwright Documentation: https://playwright.dev/python/
- CDP Protocol: https://chromedevtools.github.io/devtools-protocol/
"""

from .browser import BrowserManager
from .client import CozeClient
from .exceptions import (
    CozeError,
    CozeConnectionError,
    CozeSkillNotFoundError,
    CozeInstallationError,
    CozeInvocationError,
    CozeTaskError
)

__all__ = [
    'BrowserManager',
    'CozeClient',
    'CozeError',
    'CozeConnectionError',
    'CozeSkillNotFoundError',
    'CozeInstallationError',
    'CozeInvocationError',
    'CozeTaskError'
]
