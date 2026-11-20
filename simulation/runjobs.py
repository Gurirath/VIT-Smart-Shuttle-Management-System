import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def target(job):
    parts = job.split()
    i = parts.index("run_sim.py")
    seed, sc, out = parts[i + 1], parts[i + 2], parts[i + 3]
    return os.path.join(HERE, out, f"result_{sc}_{seed}.json")


def run(job):
    if os.path.exists(target(job)):
        return job, "skip"
    env = dict(os.environ)
    words = job.split()
    while "=" in words[0]:
        k, v = words.pop(0).split("=", 1)
        env[k] = v
    r = subprocess.run(words, cwd=HERE, env=env, capture_output=True, text=True)
    with open(os.path.join(HERE, "log_runs.txt"), "a") as f:
        f.write((r.stdout or "") + (r.stderr[-2000:] if r.returncode else ""))
    return job, r.returncode


if __name__ == "__main__":
    jobs = [l.strip() for l in open(os.path.join(HERE, "jobs.txt")) if l.strip()]
    for s in range(1, 6):
        subprocess.run([sys.executable, "build_scenario.py", str(s)], cwd=HERE, capture_output=True)
    with ThreadPoolExecutor(int(os.environ.get("WORKERS", "2"))) as ex:
        for job, rc in ex.map(run, jobs):
            if rc not in (0, "skip"):
                print("FAILED", job, flush=True)
    with open(os.path.join(HERE, "log_runs.txt"), "a") as f:
        f.write("DONE\n")
    print("DONE")
