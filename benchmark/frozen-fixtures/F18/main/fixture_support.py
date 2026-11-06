import json
import os
from pathlib import Path

def record(*parts):
    path = Path(os.environ.get("NATIVE_FIXTURE_TRACE", "fixture-trace.jsonl"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(list(parts), ensure_ascii=True) + "\n")
