from pathlib import Path
import json


class MetadataStore:
    def save(self, path: str, payload: dict) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2))
