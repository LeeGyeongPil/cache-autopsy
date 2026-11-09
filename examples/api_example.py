import json
from cache_autopsy import analyze_records, diff_requests

with open("src/cache_autopsy/samples/anthropic_broken.jsonl") as f:
    records = [json.loads(line) for line in f]
report = analyze_records(records)
print(report.summary["hit_rate"], report.summary["missed_tokens"])
for p in report.pairs[:3]:
    print(p.verdict, p.causes, p.divergence.json_path)

div = diff_requests(records[1]["request"], records[2]["request"])
print(div.reason, div.causes, div.json_path, div.byte_offset)
