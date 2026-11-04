import json
import os
from glob import glob

from stats import summarise

HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
for d, name in [(os.path.join(HERE, "results"), "main")] + \
        [(p, os.path.basename(p)) for p in sorted(glob(os.path.join(HERE, "results_grid", "*")))] + \
        [(p, os.path.basename(p)) for p in sorted(glob(os.path.join(HERE, "results_sens", "*")))]:
    runs = {}
    for f in sorted(glob(os.path.join(d, "result_*.json"))):
        key = os.path.basename(f)[len("result_"):-len(".json")]
        runs[key] = summarise(json.load(open(f)))
    if runs:
        out[name] = runs
json.dump(out, open(os.path.join(HERE, "results", "run_summaries.json"), "w"), indent=1)
print({k: len(v) for k, v in out.items()})
