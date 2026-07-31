from __future__ import annotations

from pathlib import Path

from aa_content.persistence import WorkspaceRepository


def initialize_workspace(workspace: Path) -> bool:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "research-library").mkdir(exist_ok=True)
    (workspace / "outputs").mkdir(exist_ok=True)
    return WorkspaceRepository(workspace).initialize_database()
