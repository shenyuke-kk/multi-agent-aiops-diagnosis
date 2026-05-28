import json
from pathlib import Path

p = Path("data/mock_logs/all_logs.jsonl")
print("exists=", p.exists(), "path=", p.resolve())

c = 0
with open(p, encoding="utf-8") as f:
    for line in f:
        x = json.loads(line)
        if x.get("service") == "web-service" and x.get("level") == "ERROR":
            print(x)
            c += 1
            if c >= 5:
                break

print("error_count_sample=", c)