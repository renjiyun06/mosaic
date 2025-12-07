from pathlib import Path

def mosaic_db_path() -> Path:
    return Path.home() / ".mosaic" / "mosaic.db"

def mesh_path(mesh_id: str) -> Path:
    return Path.home() / ".mosaic" / mesh_id

def node_pid_path(mesh_id: str, node_id: str) -> Path:
    return mesh_path(mesh_id) / "nodes" / f"{node_id}" / "pid"

def node_sock_path(mesh_id: str, node_id: str) -> Path:
    return mesh_path(mesh_id) / "nodes" / f"{node_id}" / "sock"

def node_lock_path(mesh_id: str, node_id: str) -> Path:
    return mesh_path(mesh_id) / "nodes" / f"{node_id}" / "lock"

def cc_hook_server_sock_path(
    mesh_id: str, node_id: str
) -> Path:
    return mesh_path(mesh_id) / "nodes" / f"{node_id}" / "cc_hook_server.sock"

def sqlite_transport_db_path(mesh_id: str) -> Path:
    return mesh_path(mesh_id) / "events.db"

def mcp_server_sock_path(mesh_id: str, node_id: str) -> Path:
    return mesh_path(mesh_id) / "nodes" / f"{node_id}" / "mcp_server.sock"