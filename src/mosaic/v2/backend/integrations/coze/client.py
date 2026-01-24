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
            skill_id: Skill ID (must be already installed)
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

            # Navigate to skill activation URL
            logger.debug(f"Activating skill with URL: ?skills={skill_id}")
            activation_url = f"https://www.coze.cn/?skills={skill_id}"
            await page.goto(activation_url)

            # Wait longer for page to fully load and skill to be auto-filled
            await asyncio.sleep(2)

            # Locate input box
            logger.debug("Locating input box...")
            input_box = page.get_by_role("textbox")

            # Wait for input box to be visible
            try:
                await input_box.wait_for(state='visible', timeout=5000)
            except Exception as e:
                raise CozeInvocationError(f"Input box not found - skill may not be installed: {e}")

            logger.debug("Input box found")

            # Wait a moment for auto-fill to complete (skill name should be auto-filled)
            await asyncio.sleep(1)

            # Click input box to focus
            await input_box.click()

            # Wait a bit after clicking
            await asyncio.sleep(0.5)

            # Move cursor to end and add user's prompt
            # Press End key to move to end of existing content
            await input_box.press("End")

            # Add a space if not already present, then add the prompt
            await input_box.type(" " + prompt, delay=50)  # Type with 50ms delay between keys

            # Wait before submitting to ensure all content is filled
            await asyncio.sleep(1)

            # Submit the task
            logger.debug("Submitting task...")
            await input_box.press("Enter")

            # Wait for redirect to task page
            logger.debug("Waiting for task creation...")
            try:
                await page.wait_for_url("https://www.coze.cn/task/*", timeout=10000)
            except Exception as e:
                raise CozeInvocationError(f"Failed to create task - timeout waiting for redirect: {e}")

            # Extract task URL and ID
            task_url = page.url

            # Parse task_id from URL
            # Format: https://www.coze.cn/task/7598770107879686438 or /task/7598770107879686438?params
            if '/task/' in task_url:
                task_id = task_url.split('/task/')[1]
                # Remove query parameters if present
                if '?' in task_id:
                    task_id = task_id.split('?')[0]
            else:
                raise CozeInvocationError(f"Invalid task URL format: {task_url}")

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
