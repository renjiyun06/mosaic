"""
Coze Platform Client
====================

High-level async client for interacting with the Coze (扣子) platform.

This module provides the main CozeClient class that implements four core
operations: search, install, invoke, and retrieve results for Coze skills.

Architecture:
    CozeClient → BrowserManager → Playwright + CDP → Coze Platform

Performance:
    - Search: 1-2 seconds (API interception, 20x faster than DOM parsing)
    - Install: 2-5 seconds
    - Invoke: 1-3 seconds
    - Get Result: Varies by task complexity (supports polling)

Usage Example:
    client = CozeClient(cdp_url="http://192.168.1.4:19222")

    # Search for skills
    skills = await client.search_skill("数据分析", max_results=5)

    # Install skill
    await client.install_skill(skill_id=skills[0]['skill_id'])

    # Invoke skill
    task = await client.invoke_skill(
        skill_id=skills[0]['skill_id'],
        prompt="分析这份销售数据"
    )

    # Get result (with polling)
    result = await client.get_result(
        task_id=task['task_id'],
        wait=True,
        timeout=120
    )
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

from .browser import BrowserManager
from .exceptions import (
    CozeError,
    CozeConnectionError,
    CozeSkillNotFoundError,
    CozeInstallationError,
    CozeInvocationError,
    CozeTaskError
)


logger = logging.getLogger(__name__)


class CozeClient:
    """
    High-level client for Coze platform operations.

    Uses BrowserManager for underlying browser automation via Playwright + CDP.
    All methods are async for non-blocking I/O.
    """

    def __init__(self, cdp_url: str = "http://192.168.1.4:19222"):
        """
        Initialize Coze client.

        Args:
            cdp_url: Chrome DevTools Protocol endpoint URL
        """
        self.cdp_url = cdp_url
        self.browser_manager = None
        logger.info(f"CozeClient initialized with CDP URL: {cdp_url}")

    # ============================================================================
    # Core Methods (Public API)
    # ============================================================================

    async def search_skill(
        self,
        keyword: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for skills on Coze platform by keyword.

        Implementation uses API interception of /api/marketplace/product/list
        for 20x performance improvement over DOM parsing.

        Args:
            keyword: Search keyword (e.g., "数据分析", "写小说")
            max_results: Maximum number of results to return

        Returns:
            List of skill dictionaries:
            [
                {
                    "skill_id": "7594680716416499753",
                    "name": "数据分析技能",
                    "description": "处理上传数据集、分析训练及可视化...",
                    "category": "开发辅助",
                    "developer": "louwill",
                    "version": "v1.1",
                    "price": "免费",
                    "usage_count": "3.4K",
                    "is_open_source": false,
                    "share_url": "https://www.coze.cn/?skill_share_pid=..."
                },
                ...
            ]

        Raises:
            ConnectionError: If browser connection fails
            TimeoutError: If search takes too long
            ValueError: If keyword is empty
        """
        # Validate inputs
        if not keyword or not keyword.strip():
            raise ValueError("Keyword cannot be empty")

        logger.info(f"Searching for skills with keyword: {keyword}")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Storage for captured API data
            captured_data = []

            # Define response handler for API interception
            async def handle_response(response):
                """Intercept API responses"""
                if '/api/marketplace/product/list' in response.url:
                    try:
                        url = response.url
                        # Check if this is a search request (has keyword parameter)
                        has_keyword = 'keyword=' in url

                        if has_keyword:
                            data = await response.body()
                            import json
                            parsed_data = json.loads(data)
                            product_count = len(parsed_data.get('data', {}).get('products', []))
                            logger.debug(f"Captured search API ({product_count} skills found)")
                            captured_data.append(parsed_data)
                    except Exception as e:
                        logger.warning(f"Error intercepting API: {e}")

            # Register response handler BEFORE navigation
            page.on('response', handle_response)

            # Navigate to skills page to ensure we're starting fresh
            logger.debug("Navigating to skills page...")
            await page.goto("https://www.coze.cn/skills")
            await asyncio.sleep(2)

            # Find search input box
            logger.debug("Locating search input box...")
            search_input = page.get_by_placeholder("搜索技能商店")

            # Clear existing content first
            await search_input.click()
            await search_input.press("Control+A")
            await search_input.press("Backspace")

            # Type keyword and trigger search
            logger.debug(f"Typing keyword: {keyword}")
            await search_input.fill(keyword)

            # Press Enter to trigger search API
            logger.debug("Triggering search...")
            await search_input.press("Enter")

            # Wait for API response
            await asyncio.sleep(2)

            # Remove handler to prevent duplicate captures
            try:
                page.remove_listener('response', handle_response)
            except Exception as e:
                logger.debug(f"Failed to remove listener (expected): {e}")

            if not captured_data:
                logger.warning("No API response captured")
                return []

            # Extract skills from API response
            api_data = captured_data[-1]  # Get the most recent response
            products = api_data.get('data', {}).get('products', [])

            logger.info(f"API returned {len(products)} skills")

            # Parse and structure the data
            skills = []
            for product in products[:max_results]:
                skill = await self._parse_skill_from_api(product)
                if skill:
                    skills.append(skill)

            logger.info(f"Successfully parsed {len(skills)} skills")
            return skills

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise CozeError(f"Failed to search skills: {e}") from e

    async def install_skill(
        self,
        skill_id: str,
        skill_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a skill to user's Coze platform account, enabling it for invocation.

        This operation adds the skill to the user's account on Coze platform,
        NOT to the local system or Mosaic node. Once added, the skill can be
        invoked via invoke_skill() method.

        If skill is already added, returns success immediately.
        Monitors button state transitions to detect completion.

        Args:
            skill_id: Skill ID (19-digit identifier)
            skill_name: Optional skill name for verification

        Returns:
            {
                "skill_id": "7594680716416499753",
                "skill_name": "数据分析技能",
                "status": "installed",  # or "already_installed"
                "message": "Successfully added skill to account"
            }

        Raises:
            ValueError: If skill_id is invalid
            TimeoutError: If operation takes too long (>10s)
            RuntimeError: If skill not found on page
            CozeInstallationError: If operation fails
        """
        # Validate inputs
        if not skill_id or not skill_id.strip():
            raise ValueError("skill_id cannot be empty")

        logger.info(f"Installing skill: {skill_id}")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Navigate to skills page
            current_url = page.url
            if "coze.cn/skills" not in current_url:
                logger.debug("Navigating to skills store...")
                await page.goto("https://www.coze.cn/skills")
                await asyncio.sleep(2)

            # Search for skill if skill_name provided (for finding the card)
            # Otherwise, try to find by skill_id in the page
            if skill_name:
                logger.debug(f"Searching for skill by name: {skill_name}")
                search_input = page.get_by_placeholder("搜索技能商店")

                # Clear existing content
                await search_input.click()
                await search_input.press("Control+A")
                await search_input.press("Backspace")

                # Type and search
                await search_input.fill(skill_name)
                await search_input.press("Enter")
                await asyncio.sleep(2)

            # Find skill card
            logger.debug("Looking for skill card...")
            skill_cards = await page.locator('.group.flex.flex-col.justify-between.border.rounded-lg').all()
            logger.debug(f"Found {len(skill_cards)} skill cards")

            skill_card = None
            for card in skill_cards:
                card_text = await card.inner_text()

                # Match by skill_id (primary) or skill_name (fallback)
                if skill_id in card_text or (skill_name and skill_name in card_text):
                    logger.debug("Found matching skill card")
                    skill_card = card
                    break

            if not skill_card:
                error_msg = f"Skill not found on page (skill_id={skill_id})"
                logger.error(error_msg)
                raise CozeSkillNotFoundError(error_msg)

            # Click skill card to open detail dialog
            logger.debug("Clicking skill card to open details...")
            await skill_card.click()
            await asyncio.sleep(1.5)

            # Wait for dialog to appear
            dialog = page.locator('[role="dialog"]')
            if not await dialog.is_visible():
                raise CozeInstallationError("Detail dialog did not appear")

            logger.debug("Detail dialog opened")

            # Find install/use button
            buttons = await dialog.locator('button').all()

            install_button = None
            button_text = None
            for btn in buttons:
                text = await btn.inner_text()
                text = text.strip()
                if text in ['安装', '使用']:
                    install_button = btn
                    button_text = text
                    logger.debug(f"Found button with text: {button_text}")
                    break

            if not install_button:
                # Close dialog before raising error
                await self._close_dialog(page, dialog)
                raise CozeInstallationError("Install/Use button not found")

            # Check if already installed
            if button_text == '使用':
                logger.info("Skill is already added to account")
                await self._close_dialog(page, dialog)
                return {
                    "skill_id": skill_id,
                    "skill_name": skill_name or "Unknown",
                    "status": "already_installed",
                    "message": "Skill is already added to your Coze account"
                }

            # Click install button
            logger.debug("Clicking install button...")
            await install_button.click()

            # Wait for installation to complete (button changes to "使用")
            logger.debug("Waiting for installation to complete...")
            max_wait_time = 10  # seconds
            start_time = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start_time < max_wait_time:
                await asyncio.sleep(0.5)

                # Re-find buttons (they may be re-rendered)
                buttons = await dialog.locator('button').all()
                for btn in buttons:
                    text = await btn.inner_text()
                    text = text.strip()
                    if text == '使用':
                        elapsed = asyncio.get_event_loop().time() - start_time
                        logger.info(f"Skill added to account in {elapsed:.1f} seconds")

                        # Close dialog
                        await asyncio.sleep(0.5)
                        await self._close_dialog(page, dialog)

                        return {
                            "skill_id": skill_id,
                            "skill_name": skill_name or "Unknown",
                            "status": "installed",
                            "message": "Successfully added skill to your Coze account"
                        }

            # Timeout
            logger.error(f"Skill installation timeout after {max_wait_time} seconds")
            await self._close_dialog(page, dialog)
            raise TimeoutError(f"Skill installation timeout after {max_wait_time} seconds")

        except (CozeInstallationError, CozeSkillNotFoundError, TimeoutError, ValueError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to add skill to account: {e}")
            raise CozeInstallationError(f"Failed to add skill to account: {e}") from e

    async def invoke_skill(
        self,
        skill_id: str,
        prompt: str
    ) -> Dict[str, Any]:
        """
        Invoke a skill with a task prompt.

        Uses URL-based activation (https://www.coze.cn/?skills={skill_id})
        for reliability. Does NOT wait for task completion.

        Args:
            skill_id: Skill ID (19-digit identifier)
                     Example: "7594680716416499753"
            prompt: Task description/instruction for the skill

        Returns:
            {
                "task_id": "7598770107879686438",
                "task_url": "https://www.coze.cn/task/7598770107879686438",
                "skill_id": "7594680716416499753",
                "status": "submitted",
                "prompt": "Original prompt text"
            }

        Raises:
            ValueError: If skill_id or prompt is empty
            RuntimeError: If skill not installed
            TimeoutError: If submission takes too long
            CozeInvocationError: If invocation fails
        """
        # Validate inputs
        if not skill_id or not skill_id.strip():
            raise ValueError("skill_id cannot be empty")
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        logger.info(f"Invoking skill: {skill_id}")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Ensure we're on Coze domain for API calls to work
            if not page.url.startswith("https://www.coze.cn"):
                logger.debug("Navigating to Coze homepage...")
                await page.goto("https://www.coze.cn/")
                await asyncio.sleep(1)

            # Step 1: Create task via API
            logger.debug("Creating task via API...")
            create_task_result = await page.evaluate("""
                async () => {
                    const response = await fetch('https://www.coze.cn/api/coze_space/create_task', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            task_name: "未命名任务",
                            task_type: 1,
                            mcp_tool_list: [],
                            source_from: 0
                        })
                    });

                    const data = await response.json();
                    return {
                        status: response.status,
                        data: data
                    };
                }
            """)

            # Check create_task response
            if create_task_result['status'] != 200:
                error_msg = create_task_result.get('data', {}).get('msg', 'Unknown error')
                raise CozeInvocationError(f"Failed to create task: {error_msg}")

            # Extract task_id from response
            task_data = create_task_result.get('data', {}).get('data', {}).get('task', {})
            task_id = task_data.get('task_id')

            if not task_id:
                raise CozeInvocationError("No task_id in create_task response")

            logger.debug(f"Task created: {task_id}")

            # Step 2: Invoke skill via chat API
            logger.debug(f"Invoking skill via chat API (prompt length: {len(prompt)} chars)...")

            # Escape prompt for JavaScript string
            escaped_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

            chat_result = await page.evaluate(f"""
                async () => {{
                    const payload = {{
                        task_id: "{task_id}",
                        query: "{escaped_prompt}",
                        files: [],
                        chat_type: "query",
                        task_run_mode: 2,
                        disable_team_mode: false,
                        all_authorized_mcp: true,
                        reference_template_list: [],
                        agent_ids: [],
                        favorites: [],
                        extra_info: {{
                            ab_config: "{{}}"
                        }},
                        reference_content: "",
                        guiding_id: "",
                        skill_id_list: ["{skill_id}"],
                        thinking: false,
                        reference_items: []
                    }};

                    const response = await fetch('https://www.coze.cn/api/coze_space/chat', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify(payload)
                    }});

                    const data = await response.json();
                    return {{
                        status: response.status,
                        data: data
                    }};
                }}
            """)

            # Check chat response
            if chat_result['status'] != 200:
                error_msg = chat_result.get('data', {}).get('msg', 'Unknown error')
                raise CozeInvocationError(f"Failed to invoke skill: {error_msg}")

            chat_data = chat_result.get('data', {})
            if chat_data.get('code') != 0:
                error_msg = chat_data.get('msg', 'Unknown error')
                raise CozeInvocationError(f"Skill invocation failed: {error_msg}")

            logger.debug("Skill invoked successfully")

            # Step 3: Navigate to task page
            task_url = f"https://www.coze.cn/task/{task_id}"
            logger.debug(f"Navigating to task page: {task_url}")
            await page.goto(task_url)

            logger.info(f"Task created: task_id={task_id}")

            return {
                "task_id": task_id,
                "task_url": task_url,
                "skill_id": skill_id,
                "status": "submitted",
                "prompt": prompt
            }

        except (CozeInvocationError, ValueError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to invoke skill: {e}")
            raise CozeInvocationError(f"Failed to invoke skill: {e}") from e

    async def get_result(
        self,
        task_id: str,
        wait: bool = True,
        timeout: int = 120,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Get task execution result, optionally waiting for completion.

        Polls API endpoint /api/coze_space/get_message_list until task
        completes (status=3) or timeout is reached.

        Args:
            task_id: Task ID from invoke_skill()
            wait: Whether to poll until completion
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            {
                "task_id": "7598770107879686438",
                "task_url": "https://www.coze.cn/task/7598770107879686438",
                "status": "completed",  # or "creating", "running", "failed"
                "reply": "AI response text (markdown formatted)...",
                "files": [
                    {
                        "name": "sales_data.csv",
                        "url": "https://space-static.coze.site/.../sales_data.csv?sign=...",
                        "uri": "7598770107879686438/sales_data-xxx.csv",
                        "id": "7598771039124046143",
                        "create_time": 1769226782095
                    },
                    ...
                ]
            }

        Important:
            File URLs contain time-limited signatures. Download immediately.

        Raises:
            ValueError: If task_id is invalid
            TimeoutError: If task doesn't complete within timeout
            CozeTaskError: If task fails (status=4)
        """
        # Validate inputs
        if not task_id or not task_id.strip():
            raise ValueError("task_id cannot be empty")

        logger.info(f"Getting result for task: {task_id} (wait={wait})")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Get API response (with polling if wait=True)
            if wait:
                api_response = await self._wait_for_task_completion(
                    task_id, timeout, poll_interval
                )
            else:
                # Get current status without waiting
                logger.debug("Getting current task status...")
                api_response = await self._fetch_task_status(page, task_id)

            # Extract task status
            data = api_response.get('data', {})
            task_status = data.get('task_status', 0)
            status_names = {1: 'creating', 2: 'running', 3: 'completed', 4: 'failed'}
            status_name = status_names.get(task_status, 'unknown')

            # Check for failed status
            if task_status == 4:
                raise CozeTaskError(f"Task failed (status={task_status})")

            # Extract results
            messages = data.get('messages', [])
            reply = await self._extract_reply_text(messages)
            files = await self._extract_files(messages)

            logger.info(f"Result extracted: status={status_name}, files={len(files)}, reply_length={len(reply)}")

            return {
                "task_id": task_id,
                "task_url": f"https://www.coze.cn/task/{task_id}",
                "status": status_name,
                "reply": reply,
                "files": files
            }

        except (CozeTaskError, ValueError, TimeoutError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to get task result: {e}")
            raise CozeTaskError(f"Failed to get task result: {e}") from e

    async def create_skill(
        self,
        description: str,
        space_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new skill on Coze platform with natural language description.

        This method submits a skill creation request using the Coze platform's
        AI-powered skill generation feature. The platform will use the provided
        description to automatically generate the skill code and configuration.

        Args:
            description: Natural language description of the skill to create
                        (e.g., "创建一个计算器技能", "Create a weather query skill")
            space_id: Optional workspace/space ID. If not provided, uses default
                     workspace from user's session

        Returns:
            Dictionary containing:
                - project_id (str): Unique identifier for the created project (19-digit)
                - project_type (int): Project type (5 = Skill)

        Raises:
            ValueError: If description is empty or invalid
            CozeConnectionError: If browser connection fails
            CozeError: If API request fails

        Example:
            result = await client.create_skill("创建一个计算器技能")
            project_id = result['project_id']  # "7599215566771093544"
        """
        import json

        # Validate inputs
        if not description or not description.strip():
            raise ValueError("description cannot be empty")

        logger.info(f"Creating skill with description: {description[:50]}...")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Always navigate to home page before UI interaction
            if page.url != "https://code.coze.cn/home":
                logger.debug("Navigating to code.coze.cn/home...")
                await page.goto("https://code.coze.cn/home", wait_until="networkidle")
                await asyncio.sleep(2)  # Wait for page to fully load
                logger.debug(f"Navigated to: {page.url}")

            # Wait for page to fully load and tabs to be available
            logger.debug("Waiting for page to load...")
            await asyncio.sleep(2)

            # Click "技能" tab
            logger.debug("Clicking '技能' tab...")
            skill_tab_clicked = await page.evaluate("""
                async () => {
                    const tabs = document.querySelectorAll('[role="tab"]');
                    console.log('Found tabs:', tabs.length);
                    for (const tab of tabs) {
                        if (tab.textContent.trim() === '技能') {
                            console.log('Found 技能 tab, focusing and clicking...');
                            tab.focus();
                            tab.click();
                            // Wait for React to update state
                            await new Promise(resolve => setTimeout(resolve, 300));
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if skill_tab_clicked:
                logger.debug("Successfully clicked '技能' tab")
                await asyncio.sleep(1)  # Wait for tab state to update
            else:
                logger.error("Could not find '技能' tab")
                raise CozeError("Could not find '技能' tab")

            # Wait for text input box to be loaded and ready
            logger.debug("Waiting for text input box to load...")
            await asyncio.sleep(2)  # Wait for input box to fully load after tab switch

            # Step 1: Find and clear the text input box
            logger.debug("Finding text input box...")
            input_found = await page.evaluate("""
                () => {
                    // Find the main multiline textbox
                    const textboxes = document.querySelectorAll('[role="textbox"]');
                    console.log('Found textboxes:', textboxes.length);

                    for (const textbox of textboxes) {
                        const rect = textbox.getBoundingClientRect();
                        console.log('Textbox visible:', rect.width, rect.height);
                        if (rect.width > 100 && rect.height > 30) {
                            console.log('Found main textbox, clearing content');
                            // Clear existing content
                            textbox.textContent = '';
                            textbox.innerText = '';

                            // Dispatch events to notify the page
                            textbox.dispatchEvent(new Event('input', { bubbles: true }));
                            textbox.dispatchEvent(new Event('change', { bubbles: true }));
                            textbox.focus();
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if not input_found:
                logger.error("Could not find text input box")
                raise CozeError("Could not find text input box")

            logger.debug("Cleared input box")
            await asyncio.sleep(0.3)

            # Step 2: Fill the text input box with description
            logger.debug(f"Filling input with: {description}")
            fill_success = await page.evaluate("""
                (description) => {
                    const textboxes = document.querySelectorAll('[role="textbox"]');

                    for (const textbox of textboxes) {
                        const rect = textbox.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 30) {
                            console.log('Filling textbox with description');
                            // Fill with description
                            textbox.textContent = description;
                            textbox.innerText = description;

                            // Dispatch events to notify the page
                            textbox.dispatchEvent(new Event('input', { bubbles: true }));
                            textbox.dispatchEvent(new Event('change', { bubbles: true }));
                            textbox.focus();
                            return true;
                        }
                    }
                    return false;
                }
            """, description)

            if not fill_success:
                logger.error("Could not fill text input box")
                raise CozeError("Could not fill text input box")

            logger.debug(f"Successfully filled input with: {description}")
            await asyncio.sleep(0.5)

            # Set up network request listener to capture the API response
            logger.debug("Setting up network listener...")

            # We'll use CDP session to listen for network responses
            cdp_session = await page.context.new_cdp_session(page)
            await cdp_session.send('Network.enable')

            captured_response = {}

            async def handle_response(params):
                if 'create_vibe_project' in params.get('response', {}).get('url', ''):
                    request_id = params['requestId']
                    # Get response body
                    try:
                        response_body = await cdp_session.send('Network.getResponseBody', {'requestId': request_id})
                        captured_response['data'] = json.loads(response_body['body'])
                        logger.debug("Captured API response from network!")
                    except Exception as e:
                        logger.warning(f"Could not get response body: {e}")

            cdp_session.on('Network.responseReceived', handle_response)

            # Press Enter to submit
            logger.debug("Pressing Enter to submit...")
            await page.keyboard.press('Enter')

            # Wait for the API call to complete
            logger.debug("Waiting for API response...")
            for i in range(20):  # Wait up to 10 seconds
                if captured_response:
                    break
                await asyncio.sleep(0.5)

            if not captured_response:
                logger.warning("Did not capture network response")
                raise CozeError("Did not capture network response")

            # Process captured response
            response = captured_response['data']
            logger.debug(f"Captured API Response: {json.dumps(response, ensure_ascii=False)}")

            # Check response
            if response.get('code') != 0:
                error_msg = response.get('msg') or response.get('message', 'Unknown error')
                raise CozeError(f"Failed to create skill: {error_msg}")

            # Extract result
            data = response.get('data', {})
            project_id = data.get('project_id')
            project_type = data.get('project_type')

            if not project_id:
                raise CozeError("No project_id in API response")

            logger.info(f"Skill creation submitted: project_id={project_id}, project_type={project_type}")

            return {
                "project_id": project_id,
                "project_type": project_type
            }

        except (CozeError, ValueError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to create skill: {e}")
            raise CozeError(f"Failed to create skill: {e}") from e

    async def send_message(
        self,
        project_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send a message to the Coze skill creation agent.

        Args:
            project_id: Project ID (19-digit identifier)
            message: Message to send to the agent

        Returns:
            Dictionary containing:
                - success (bool): Whether message was sent successfully
                - project_id (str): Project identifier

        Raises:
            ValueError: If project_id or message is invalid
            CozeTaskError: If unable to send message
            CozeConnectionError: If browser connection fails
        """
        # Validate inputs
        if not project_id or not project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not message or not message.strip():
            raise ValueError("message cannot be empty")

        logger.info(f"Sending message to project {project_id}: {message[:50]}...")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Navigate to project page
            project_url = f"https://code.coze.cn/p/{project_id}"
            logger.debug(f"Navigating to project page: {project_url}")
            await page.goto(project_url, wait_until="networkidle")

            # Wait for the CodeMirror input box to appear and be ready
            logger.debug("Waiting for input box to load...")
            await page.wait_for_selector('.cm-content[role="textbox"]', timeout=10000)
            await asyncio.sleep(2)  # Extra time for CodeMirror to fully initialize

            # Click on the input box to focus it
            logger.debug("Clicking on input box...")
            await page.click('.cm-content[role="textbox"]')
            await asyncio.sleep(0.3)

            # Hack: First type empty string to trigger events
            await page.keyboard.type('')
            await asyncio.sleep(0.3)

            # Then type the actual message
            logger.debug("Typing message...")
            await page.keyboard.type(message)
            await asyncio.sleep(0.5)

            # Press Enter to send
            logger.debug("Pressing Enter to send message...")
            await page.keyboard.press('Enter')
            await asyncio.sleep(1)

            logger.info(f"Message sent successfully to project {project_id}")

            return {
                "success": True,
                "project_id": project_id
            }

        except (CozeTaskError, ValueError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise CozeTaskError(f"Failed to send message: {e}") from e

    async def get_agent_response(
        self,
        project_id: str,
        timeout: int = 300,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Wait for and get the latest response from Coze skill creation agent.

        This method waits until the agent stops generating (stop button disappears),
        then returns the agent's latest response.

        Args:
            project_id: Project ID (19-digit identifier)
            timeout: Maximum wait time in seconds (default: 300)
            poll_interval: Polling interval in seconds (default: 3)

        Returns:
            Dictionary containing:
                - project_id (str): Project identifier
                - agent_response (str): Complete agent response text

        Raises:
            ValueError: If project_id is invalid
            TimeoutError: If agent doesn't complete within timeout
            CozeTaskError: If unable to get response
            CozeConnectionError: If browser connection fails
        """
        # Validate inputs
        if not project_id or not project_id.strip():
            raise ValueError("project_id cannot be empty")

        logger.info(f"Waiting for agent response: project_id={project_id}, timeout={timeout}s")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Navigate to project page if needed
            project_url = f"https://code.coze.cn/p/{project_id}"
            if page.url != project_url:
                logger.debug(f"Navigating to project page: {project_url}")
                await page.goto(project_url, wait_until="networkidle")
                await asyncio.sleep(2)

            # Poll until agent stops generating
            start_time = asyncio.get_event_loop().time()

            while True:
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Agent did not complete response within {timeout} seconds"
                    )

                # Check if agent is still generating and get latest response
                logger.debug(f"Polling agent status (elapsed: {elapsed:.1f}s)")
                check_result = await page.evaluate("""
                    () => {
                        // Check if stop button exists (indicates agent is still generating)
                        const stopButton = document.querySelector('.bg-primary.cursor-pointer.rounded-max');
                        const isGenerating = stopButton !== null;

                        // Get the latest agent response
                        let agentResponse = '';

                        try {
                            // Find the conversation container
                            const scrollContainer = document.querySelector('.scrollbar-uKmmSj');
                            if (!scrollContainer) {
                                return { isGenerating, agentResponse, error: 'Conversation container not found' };
                            }

                            // Get all message blocks
                            const messageBlocks = Array.from(scrollContainer.children).filter(child =>
                                child.className.includes('w-full') && child.innerText.trim().length > 0
                            );

                            if (messageBlocks.length === 0) {
                                return { isGenerating, agentResponse, error: 'No messages found' };
                            }

                            // Get the last message block
                            const lastBlock = messageBlocks[messageBlocks.length - 1];

                            // Extract agent reply (has 'group/assistant-message-group' class)
                            const assistantMessage = lastBlock.querySelector('.group\\\\/assistant-message-group');

                            if (assistantMessage) {
                                agentResponse = assistantMessage.innerText;
                            } else {
                                return { isGenerating, agentResponse, error: 'Agent message not found in last block' };
                            }
                        } catch (e) {
                            return { isGenerating, agentResponse, error: e.toString() };
                        }

                        return { isGenerating, agentResponse };
                    }
                """)

                is_generating = check_result.get('isGenerating', False)
                agent_response = check_result.get('agentResponse', '')
                error = check_result.get('error')

                if error:
                    logger.debug(f"Polling error: {error}")

                logger.debug(f"Agent generating: {is_generating}, response length: {len(agent_response)}")

                # If not generating, we're done
                if not is_generating:
                    logger.info(f"Agent response received (length: {len(agent_response)} chars)")

                    return {
                        "project_id": project_id,
                        "agent_response": agent_response
                    }

                # Still generating, wait and retry
                logger.debug(f"Agent still generating, waiting {poll_interval}s...")
                await asyncio.sleep(poll_interval)

        except (CozeTaskError, ValueError, TimeoutError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to get agent response: {e}")
            raise CozeTaskError(f"Failed to get agent response: {e}") from e

    async def deploy_skill(
        self,
        project_id: str,
        deploy_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deploy a skill to Coze platform.

        This method submits a deployment request for a created skill, making it
        available for use on the Coze platform.

        Args:
            project_id: Project ID from create_skill() (19-digit identifier)
            deploy_name: Optional deployment name. If not provided, uses project name

        Returns:
            Dictionary containing:
                - deploy_history_id (str): Unique identifier for the deployment (19-digit)
                - prev_deploy_history_id (str): Previous deployment ID, or "0" if first deployment
                - project_id (str): Associated project identifier

        Raises:
            ValueError: If project_id is invalid
            CozeConnectionError: If browser connection fails
            CozeError: If deployment request fails

        Example:
            result = await client.deploy_skill("7599215566771093544")
            deploy_history_id = result['deploy_history_id']
        """
        # Validate inputs
        if not project_id or not project_id.strip():
            raise ValueError("project_id cannot be empty")

        logger.info(f"Deploying skill: project_id={project_id}")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Ensure we're on code.coze.cn domain for API calls to work
            if not page.url.startswith("https://code.coze.cn"):
                logger.debug("Navigating to code.coze.cn...")
                await page.goto("https://code.coze.cn/home")
                await asyncio.sleep(1)

            # Step 1: Encrypt project secrets
            encrypt_api_url = "https://code.coze.cn/api/permission_api/project_secret/encrypt_project_secret"
            encrypt_request_body = {
                "project_id": project_id,
                "encrypt_secrets": {"secrets": []}
            }

            logger.debug(f"Encrypting project secrets: {encrypt_api_url}")

            # Make encryption API request
            encrypt_response = await page.evaluate("""
                async (args) => {
                    const response = await fetch(args.url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'x-requested-with': 'XMLHttpRequest',
                            'Agw-Js-Conv': 'str'
                        },
                        body: JSON.stringify(args.body)
                    });
                    return await response.json();
                }
            """, {"url": encrypt_api_url, "body": encrypt_request_body})

            # Check encryption response
            if encrypt_response.get('code') != 0:
                error_msg = encrypt_response.get('msg') or encrypt_response.get('message', 'Unknown error')
                raise CozeError(f"Failed to encrypt project secrets: {error_msg}")

            # Extract sealed_secrets
            sealed_secrets = encrypt_response.get('data', {}).get('sealed_secrets', '')
            logger.debug(f"Obtained sealed secrets: {sealed_secrets[:50]}...")

            # Step 2: Create deployment with encrypted secrets
            deploy_api_url = "https://code.coze.cn/api/coding/deployment/deploy_history/create"
            deploy_request_body = {
                "project_id": project_id,
                "encrypt_env_variable": sealed_secrets,
                "table_sync_configs": []
            }

            logger.debug(f"Creating deployment via API: {deploy_api_url}")

            # Make deployment API request (keep project_id as string)
            response = await page.evaluate("""
                async (args) => {
                    const response = await fetch(args.url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'x-requested-with': 'XMLHttpRequest',
                            'Agw-Js-Conv': 'str'
                        },
                        body: JSON.stringify(args.body)
                    });
                    return await response.json();
                }
            """, {"url": deploy_api_url, "body": deploy_request_body})

            logger.debug(f"Deploy skill API response: {response}")

            # Check response
            if response.get('code') != 0:
                error_msg = response.get('msg') or response.get('message', 'Unknown error')
                raise CozeError(f"Failed to deploy skill: {error_msg}")

            # Extract result
            data = response.get('data', {})
            deploy_history_id = data.get('deploy_history_id')
            prev_deploy_history_id = data.get('prev_deploy_history_id')

            if not deploy_history_id:
                raise CozeError("No deploy_history_id in API response")

            logger.info(f"Skill deployment submitted: deploy_history_id={deploy_history_id}")

            return {
                "deploy_history_id": deploy_history_id,
                "prev_deploy_history_id": prev_deploy_history_id,
                "project_id": project_id
            }

        except (CozeError, ValueError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to deploy skill: {e}")
            raise CozeError(f"Failed to deploy skill: {e}") from e

    async def list_user_skills(
        self,
        skill_type: str = "created",
        keyword: str = ""
    ) -> List[Dict[str, Any]]:
        """
        List user's skills on Coze platform by type.

        This method retrieves skills from the user's account by navigating to
        the skills page and intercepting the API response.

        Args:
            skill_type: Type of skills to list
                - "created": Skills created by user (sources=1)
                - "installed": Skills installed by user (sources=2,3)
                - "all": All skills (sources=1,2,3)
            keyword: Optional keyword to filter skills

        Returns:
            List of skill dictionaries:
            [
                {
                    "skill_id": "7599503685093425192",
                    "name": "算24点技能",
                    "description": "...",
                    "source": 1,  # 1=created, 2=installed
                    "icon_url": "...",
                    "status": 1
                },
                ...
            ]

        Raises:
            ValueError: If skill_type is invalid
            CozeConnectionError: If browser connection fails
            CozeError: If API request fails

        Example:
            # Get created skills
            skills = await client.list_user_skills("created")

            # Get installed skills
            skills = await client.list_user_skills("installed")
        """
        # Validate inputs
        valid_types = ["created", "installed", "all"]
        if skill_type not in valid_types:
            raise ValueError(f"Invalid skill_type: {skill_type}. Must be one of {valid_types}")

        logger.info(f"Listing user skills: type={skill_type}, keyword='{keyword}'")

        # Initialize browser manager if not already done
        if not self.browser_manager:
            self.browser_manager = BrowserManager()

        try:
            # Connect to browser and get page
            await self.browser_manager.connect(self.cdp_url)
            page = await self.browser_manager.get_page()

            # Storage for captured API data
            captured_data = []

            # Define response handler for API interception
            async def handle_response(response):
                """Intercept API responses for user_skill endpoint"""
                if '/api/marketplace/product/skill/user_skill' in response.url:
                    try:
                        data = await response.body()
                        import json
                        parsed_data = json.loads(data)

                        if parsed_data.get('code') == 0:
                            skills_count = len(parsed_data.get('data', {}).get('skills', []))
                            logger.debug(f"Captured user skills API ({skills_count} skills found)")
                            captured_data.append(parsed_data)
                    except Exception as e:
                        logger.warning(f"Error intercepting API: {e}")

            # Register response handler BEFORE navigation
            page.on('response', handle_response)

            # Navigate to skills page with "my" tab
            logger.debug("Navigating to skills page...")
            await page.goto("https://www.coze.cn/skills?tab=my")
            await asyncio.sleep(2)  # Wait for page to load

            # Handle different skill types
            if skill_type == "all":
                # Get both created and installed skills
                logger.debug("Getting all skills (created + installed)...")

                # First, get created skills - click "我创建的"
                logger.debug("Clicking '我创建的' radio button...")
                clicked = await page.evaluate("""
                    async () => {
                        const radios = document.querySelectorAll('[role="radio"]');
                        for (const radio of radios) {
                            if (radio.textContent && radio.textContent.includes('我创建的')) {
                                radio.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if not clicked:
                    logger.warning("Could not find '我创建的' radio button")
                await asyncio.sleep(3)  # Wait for API response

                # Now click "我安装的" to get installed skills
                logger.debug("Clicking '我安装的' radio button...")
                clicked = await page.evaluate("""
                    async () => {
                        const radios = document.querySelectorAll('[role="radio"]');
                        for (const radio of radios) {
                            if (radio.textContent && radio.textContent.includes('我安装的')) {
                                radio.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if not clicked:
                    logger.warning("Could not find '我安装的' radio button")
                await asyncio.sleep(3)  # Wait for API response

            elif skill_type == "created":
                logger.debug("Clicking '我创建的' radio button...")
                clicked = await page.evaluate("""
                    async () => {
                        const radios = document.querySelectorAll('[role="radio"]');
                        for (const radio of radios) {
                            if (radio.textContent && radio.textContent.includes('我创建的')) {
                                radio.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if not clicked:
                    logger.warning("Could not find '我创建的' radio button")
                await asyncio.sleep(3)  # Wait for API response

            elif skill_type == "installed":
                # "我安装的" is selected by default, just wait for API
                logger.debug("Using default '我安装的' selection...")
                await asyncio.sleep(2)

            # Remove handler to prevent duplicate captures
            try:
                page.remove_listener('response', handle_response)
            except Exception:
                pass

            if not captured_data:
                logger.warning("No API response captured")
                return []

            # Merge all captured responses (for "all" type, we have multiple responses)
            all_skills_raw = []
            for api_data in captured_data:
                skills_in_response = api_data.get('data', {}).get('skills', [])
                all_skills_raw.extend(skills_in_response)

            logger.info(f"API returned {len(all_skills_raw)} skills total from {len(captured_data)} responses")

            # Parse and structure the data, removing duplicates by skill_id
            skills_dict = {}
            for skill_raw in all_skills_raw:
                skill_id = skill_raw.get('id', '')
                if skill_id and skill_id not in skills_dict:
                    skill = {
                        "skill_id": skill_id,
                        "name": skill_raw.get('show_name', ''),
                        "description": skill_raw.get('show_description', ''),
                        "source": skill_raw.get('source', 0),
                        "icon_url": skill_raw.get('icon_url', ''),
                        "status": skill_raw.get('status', 0),
                        "space_id": skill_raw.get('space_id', ''),
                        "owner_type": skill_raw.get('owner_type', 0)
                    }
                    skills_dict[skill_id] = skill

            skills = list(skills_dict.values())
            logger.info(f"Successfully parsed {len(skills)} unique skills")
            return skills

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to list user skills: {e}")
            raise CozeError(f"Failed to list user skills: {e}") from e

    # ============================================================================
    # Helper Methods (Private)
    # ============================================================================

    async def _parse_skill_from_api(self, product: dict) -> dict:
        """
        Parse skill metadata from API response product object.

        Extracts and normalizes fields from /api/marketplace/product/list
        response structure.

        Args:
            product: Product dictionary from API response

        Returns:
            Normalized skill dictionary with standardized fields
        """
        try:
            meta = product.get('meta_info', {})
            sell = product.get('sell_info', {})
            skill_extra = product.get('skill_extra', {})

            # Extract skill ID (entity_id is the actual skill_id, not 'id')
            skill_id = meta.get('entity_id', '')

            # Extract category name
            category = meta.get('category', {})
            category_name = category.get('name', 'Unknown') if isinstance(category, dict) else 'Unknown'

            # Extract seller/developer info
            seller = meta.get('seller', {})
            developer = seller.get('name', 'Unknown') if isinstance(seller, dict) else 'Unknown'

            # Determine price
            is_free = meta.get('is_free', True)
            price = '免费' if is_free else 'Unknown'

            # Try to get price from SKU info
            if not is_free:
                skus = sell.get('skus', {})
                for sku_id, sku_data in skus.items():
                    sku_price = sku_data.get('price', [])
                    if sku_price and len(sku_price) > 0:
                        # Price is usually in format [{"amount": 300, "currency": "CNY"}]
                        price_amount = sku_price[0].get('amount', 0)
                        if price_amount > 0:
                            price = f"¥{price_amount/100:.0f}/月"
                            break

            # Extract usage count (heat)
            heat = meta.get('heat', 0)
            if heat >= 1000:
                usage_count = f"{heat/1000:.1f}K"
            else:
                usage_count = str(heat)

            # Extract version from skill_extra
            version = skill_extra.get('show_version', 'Unknown')

            # Check if open source (determined by publish_mode)
            publish_mode = skill_extra.get('publish_mode', 0)
            is_open_source = (publish_mode == 1)  # 1 = open source, 2 = regular

            # Build structured metadata
            skill_metadata = {
                'skill_id': skill_id,
                'name': meta.get('name', 'Unknown'),
                'description': meta.get('description', ''),
                'category': category_name,
                'developer': developer,
                'version': version,
                'price': price,
                'usage_count': usage_count,
                'is_open_source': is_open_source,
                'share_url': f"https://www.coze.cn/?skill_share_pid={skill_id}"
            }

            return skill_metadata

        except Exception as e:
            logger.warning(f"Failed to parse product data: {e}")
            return None

    async def _fetch_task_status(self, page, task_id: str) -> dict:
        """
        Fetch task status from API (single call, no polling).

        Args:
            page: Playwright page object
            task_id: Task ID to query

        Returns:
            API response dictionary

        Raises:
            CozeTaskError: If API call fails
        """
        try:
            result = await page.evaluate("""
                async (taskId) => {
                    try {
                        const response = await fetch('https://www.coze.cn/api/coze_space/get_message_list', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                task_id: taskId,
                                size: 10
                            })
                        });
                        const data = await response.json();
                        return data;
                    } catch (error) {
                        return { error: error.message };
                    }
                }
            """, task_id)

            if 'error' in result:
                raise CozeTaskError(f"API call failed: {result['error']}")

            if result.get('code') != 0:
                raise CozeTaskError(f"API returned error code: {result.get('code')}, msg: {result.get('msg')}")

            return result

        except Exception as e:
            logger.error(f"Failed to fetch task status: {e}")
            raise CozeTaskError(f"Failed to fetch task status: {e}") from e

    async def _extract_reply_text(self, messages: list) -> str:
        """
        Extract AI reply text from message list.

        Searches for messages with type=2 (AI message) and extracts
        content from action_type='reply' actions.

        Args:
            messages: Messages array from API response

        Returns:
            Concatenated AI reply text
        """
        import json as json_module

        reply_parts = []

        for message in messages:
            if message.get('type') == 2:  # AI message
                steps = message.get('steps', [])
                for step in steps:
                    action_list = step.get('action_list', [])
                    for action in action_list:
                        if action.get('action_type') == 'reply':
                            content_str = action.get('content', '')
                            try:
                                # Try to parse as JSON
                                content_json = json_module.loads(content_str)
                                reply_text = content_json.get('content', '')
                                if reply_text:
                                    reply_parts.append(reply_text)
                            except json_module.JSONDecodeError:
                                # If not JSON, use as-is
                                if content_str:
                                    reply_parts.append(content_str)

        return '\n\n'.join(reply_parts)

    async def _extract_files(self, messages: list) -> list:
        """
        Extract file list from message list.

        Collects all file_list arrays from all actions and flattens
        into a single list.

        Args:
            messages: Messages array from API response

        Returns:
            List of file dictionaries with name, url, uri, id, create_time
        """
        files = []

        for message in messages:
            if message.get('type') == 2:  # AI message
                steps = message.get('steps', [])
                for step in steps:
                    action_list = step.get('action_list', [])
                    for action in action_list:
                        file_list = action.get('file_list')
                        if file_list:
                            for file_info in file_list:
                                files.append({
                                    'name': file_info.get('file_name', ''),
                                    'url': file_info.get('file_url', ''),
                                    'uri': file_info.get('file_uri', ''),
                                    'id': file_info.get('id', ''),
                                    'create_time': file_info.get('create_time', 0)
                                })

        return files

    async def _close_dialog(self, page, dialog):
        """
        Close detail dialog by clicking close button.

        Args:
            page: Playwright page object
            dialog: Dialog locator

        Note:
            Swallows exceptions silently as dialog closing is not critical
        """
        try:
            # Try to find and click close button
            # The close button may have different selectors, try common ones
            close_selectors = [
                'button:has-text("Close")',
                '[aria-label="Close"]',
                'button[aria-label="关闭"]',
                '.close-button'
            ]

            for selector in close_selectors:
                try:
                    close_btn = dialog.locator(selector).first
                    if await close_btn.is_visible(timeout=1000):
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                        logger.debug("Dialog closed successfully")
                        return
                except Exception:
                    continue

            # If no close button found, try pressing Escape
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
            logger.debug("Dialog closed with Escape key")

        except Exception as e:
            logger.debug(f"Failed to close dialog (non-critical): {e}")

    async def _wait_for_task_completion(
        self,
        task_id: str,
        timeout: int,
        poll_interval: int
    ) -> dict:
        """
        Poll task status until completion or timeout.

        Repeatedly calls /api/coze_space/get_message_list and checks
        task_status field (1=creating, 2=running, 3=completed, 4=failed).

        Args:
            task_id: Task ID to monitor
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final API response when task completes

        Raises:
            TimeoutError: If task doesn't complete in time
            CozeTaskError: If task fails (status=4)
        """
        logger.info(f"Waiting for task completion: task_id={task_id}, timeout={timeout}s")

        page = await self.browser_manager.get_page()
        start_time = asyncio.get_event_loop().time()
        poll_count = 0

        status_names = {1: 'creating', 2: 'running', 3: 'completed', 4: 'failed'}

        while asyncio.get_event_loop().time() - start_time < timeout:
            poll_count += 1
            elapsed = int(asyncio.get_event_loop().time() - start_time)

            logger.debug(f"Poll {poll_count}: checking status (elapsed: {elapsed}s)")

            # Fetch current status
            api_response = await self._fetch_task_status(page, task_id)

            # Check task status
            data = api_response.get('data', {})
            task_status = data.get('task_status', 0)
            status_name = status_names.get(task_status, f'unknown({task_status})')

            logger.debug(f"Task status: {status_name}")

            if task_status == 3:  # Completed
                logger.info(f"Task completed in {elapsed}s ({poll_count} polls)")
                return api_response

            if task_status == 4:  # Failed
                raise CozeTaskError(f"Task failed (status={task_status})")

            # Not completed yet, wait and retry
            await asyncio.sleep(poll_interval)

        # Timeout
        raise TimeoutError(f"Task did not complete within {timeout} seconds")
