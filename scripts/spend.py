"""Total spend across every recorded run, used as the overnight cost guard."""

import json
from pathlib import Path

total = 0.0
for records in Path("runs").glob("*/records.jsonl"):
    for line in records.read_text().splitlines():
        if line.strip():
            total += json.loads(line).get("cost_usd") or 0.0
print(f"{total:.2f}")
