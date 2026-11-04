SEEDS_MAIN = [1, 2, 3, 4, 5]
SEEDS_SENS = [1, 2, 3]
BETA_WAIT = [-0.15, -0.25, -0.35, -0.5, -0.7]
BETA_SEAT = [0.5, 1.0, 2.0, 3.0, 4.0]
VARIANTS = {
    "seek40": "SEEK_PROB=0.4",
    "seek80": "SEEK_PROB=0.8",
    "demand80": "DEMAND_SCALE=0.8",
    "demand120": "DEMAND_SCALE=1.2",
    "outage3x": "OUTAGE_EVERY_S=600",
    "noshelter": "SHELTER_SHARE=0.0",
}

jobs = []
for s in SEEDS_MAIN:
    for sc in ("A", "B_real", "B_oracle"):
        jobs.append(f"X=1 python3 run_sim.py {s} {sc} results")
for bw in BETA_WAIT:
    for bs in BETA_SEAT:
        if bw == -0.35 and bs == 2.0:
            continue
        tag = f"bw{bw}_bs{bs}"
        for s in SEEDS_SENS:
            jobs.append(f"BETA_WAIT={bw} BETA_SEAT={bs} python3 run_sim.py {s} B_real results_grid/{tag}")
for name, env in VARIANTS.items():
    for s in SEEDS_SENS:
        for sc in ("A", "B_real"):
            if name == "noshelter" and sc == "A":
                continue
            jobs.append(f"{env} python3 run_sim.py {s} {sc} results_sens/{name}")
print("\n".join(jobs))
