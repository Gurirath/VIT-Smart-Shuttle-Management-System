import os
import subprocess
import sys
import sumo
import sumolib

HERE = os.path.dirname(os.path.abspath(__file__))
NET = os.path.join(HERE, "corridor.net.xml")
TOOLS = os.path.join(sumo.SUMO_HOME, "tools")

STOP_POS = 260.0
STOP_LEN = 30.0
SIM_END = 3 * 3600 + 900


def corridor_edges(net):
    es = [e for e in net.getEdges()
          if e.getFromNode().getCoord()[1] == 400 and e.getToNode().getCoord()[1] == 400
          and e.getToNode().getCoord()[0] > e.getFromNode().getCoord()[0]]
    es.sort(key=lambda e: e.getFromNode().getCoord()[0])
    return es


def write_stops(edges):
    path = os.path.join(HERE, "stops.add.xml")
    with open(path, "w") as f:
        f.write("<additional>\n")
        for i, e in enumerate(edges):
            f.write(f'  <busStop id="S{i+1:02d}" lane="{e.getID()}_0" startPos="{STOP_POS}" endPos="{STOP_POS + STOP_LEN}" friendlyPos="true"/>\n')
        f.write("</additional>\n")
    return path


def write_background(seed):
    out = os.path.join(HERE, f"bg_{seed}.rou.xml")
    subprocess.run([sys.executable, os.path.join(TOOLS, "randomTrips.py"), "-n", NET, "-o", os.path.join(HERE, f"bg_{seed}.trips.xml"),
                    "-r", out, "-b", "0", "-e", str(SIM_END), "-p", "1.6", "--seed", str(seed),
                    "--fringe-factor", "5", "--min-distance", "1500", "--prefix", "bg",
                    "--trip-attributes", 'departLane="best" departSpeed="max"'],
                   check=True, capture_output=True)
    return out


def write_corridor_flow(edges, seed):
    path = os.path.join(HERE, f"corr_{seed}.rou.xml")
    route = " ".join(e.getID() for e in edges)
    with open(path, "w") as f:
        f.write("<routes>\n")
        f.write(f'  <route id="corr" edges="{route}"/>\n')
        f.write(f'  <flow id="cars" route="corr" begin="0" end="{SIM_END}" vehsPerHour="650" departLane="best" departSpeed="max"/>\n')
        f.write("</routes>\n")
    return path


def write_buses(edges, seed, headway=360, jitter=60, first=300, last=3 * 3600 + 300):
    import random
    rng = random.Random(seed)
    path = os.path.join(HERE, f"bus_{seed}.rou.xml")
    route = " ".join(e.getID() for e in edges)
    with open(path, "w") as f:
        f.write("<routes>\n")
        f.write('  <vType id="citybus" vClass="bus" length="12" maxSpeed="13.89" accel="1.0" decel="3.0" sigma="0.5" guiShape="bus"/>\n')
        f.write(f'  <route id="line21" edges="{route}"/>\n')
        t = first
        k = 0
        deps = []
        while t <= last:
            dep = max(0, t + rng.uniform(-jitter, jitter))
            deps.append((dep, k))
            k += 1
            t += headway
        deps.sort()
        for dep, k in deps:
            f.write(f'  <vehicle id="bus{k:03d}" type="citybus" route="line21" depart="{dep:.1f}" departLane="0">\n')
            for i in range(len(edges)):
                f.write(f'    <stop busStop="S{i+1:02d}" duration="9999"/>\n')
            f.write("  </vehicle>\n")
        f.write("</routes>\n")
    return path


def build(seed):
    net = sumolib.net.readNet(NET)
    edges = corridor_edges(net)
    stops = write_stops(edges)
    bg = write_background(seed)
    corr = write_corridor_flow(edges, seed)
    bus = write_buses(edges, seed)
    return {"net": NET, "stops": stops, "routes": [bg, corr, bus], "edges": [e.getID() for e in edges],
            "edge_x0": [e.getFromNode().getCoord()[0] for e in edges]}


if __name__ == "__main__":
    print(build(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
