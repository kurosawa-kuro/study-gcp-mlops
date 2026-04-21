from pathlib import Path


class ArtifactStore:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir)

    def run_dir(self, run_id: str) -> Path:
        return self.root_dir / run_id

    def latest_link(self) -> Path:
        return self.root_dir / "latest"
