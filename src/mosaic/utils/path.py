from pathlib import Path

def absolute_path(path: Path | str) -> Path:
    if isinstance(path, str):
        path = Path(path)
    
    if path.is_absolute():
        return path
    
    cwd = Path.cwd()
    return cwd / path