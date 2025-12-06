from fastmcp import FastMCP

from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

mcp = FastMCP("mosaic-mcp-server")

@mcp.tool
async def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)