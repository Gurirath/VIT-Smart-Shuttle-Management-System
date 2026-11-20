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
HEADWAY_21 = 360
HEADWAY_22 = 600
SIM_END = 3 * 3600 + 900


def corridor_edges(net):
    es = [e for e in net.getEdges()
          if e.getFromNode().getCoord()[1] == 400 and e.getToNode().getCoord()[1] == 400
          and e.getToNode().getCoord()[0] > e.getFromNode().getCoord()[0]]
    es.sort(key=lambda e: e.getFromNode().getCoord()[0])
    return es


SHARED = range(5, 15)
BRANCH_STOPS = {"N01": 600, "N02": 1800, "N03": 9600, "N04": 10800}


def edge_between(net, a, b):
    for e in net.getEdges():
        if e.getFromNode().getCoord() == a and e.getToNode().getCoord() == b:
            return e
    raise KeyError((a, b))


def branch_edges(net):
    west = [edge_between(net, (x, 800), (x + 600, 800)) for x in range(0, 3000, 600)]
    down = edge_between(net, (3000, 800), (3000, 400))
    up = edge_between(net, (9000, 400), (9000, 800))
    east = [edge_between(net, (x, 800), (x + 600, 800)) for x in range(9000, 12000, 600)]
    return west, down, up, east


def route_defs(net, edges):
    west, down, up, east = branch_edges(net)
    r22_edges = west + [down] + [edges[i] for i in SHARED] + [up] + east
    stop_edge = {f"S{i+1:02d}": e for i, e in enumerate(edges)}
    for sid, x in BRANCH_STOPS.items():
        stop_edge[sid] = edge_between(net, (x, 800), (x + 600, 800))
    names = [f"S{i+1:02d}" for i in range(len(edges))] + list(BRANCH_STOPS)
    seqs = {"21": [f"S{i+1:02d}" for i in range(len(edges))],
            "22": ["N01", "N02"] + [f"S{i+1:02d}" for i in SHARED] + ["N03", "N04"]}
    out = {}
    for r, es in (("21", edges), ("22", r22_edges)):
        cum, acc = {}, 0.0
        for e in es:
            cum[e.getID()] = acc
            acc += e.getLength()
        dist = [cum[stop_edge[s].getID()] + STOP_POS + STOP_LEN / 2 for s in seqs[r]]
        out[r] = {"edges": [e.getID() for e in es], "stops": [names.index(s) for s in seqs[r]], "stopdist": dist, "length_m": acc}
    return names, stop_edge, out


def write_stops(names, stop_edge):
    path = os.path.join(HERE, "stops2.add.xml")
    with open(path, "w") as f:
        f.write("<additional>\n")
        for sid in names:
            f.write(f'  <busStop id="{sid}" lane="{stop_edge[sid].getID()}_0" startPos="{STOP_POS}" endPos="{STOP_POS + STOP_LEN}" friendlyPos="true"/>\n')
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


def write_buses(routes, names, seed, jitter=60, first=300, last=3 * 3600 + 300):
    import random
    rng = random.Random(seed)
    path = os.path.join(HERE, f"bus2_{seed}.rou.xml")
    deps = []
    for r, headway, offset in (("21", HEADWAY_21, 0), ("22", HEADWAY_22, 150)):
        t = first + offset
        k = 0
        while t <= last:
            deps.append((max(0, t + rng.uniform(-jitter, jitter)), r, k))
            k += 1
            t += headway
    deps.sort()
    with open(path, "w") as f:
        f.write("<routes>\n")
        f.write('  <vType id="citybus" vClass="bus" length="12" maxSpeed="13.89" accel="1.0" decel="3.0" sigma="0.5" guiShape="bus"/>\n')
        for r, d in routes.items():
            f.write(f'  <route id="line{r}" edges="{" ".join(d["edges"])}"/>\n')
        for dep, r, k in deps:
            vid = f"bus{k:03d}" if r == "21" else f"bus22_{k:03d}"
            f.write(f'  <vehicle id="{vid}" type="citybus" route="line{r}" depart="{dep:.1f}" departLane="0">\n')
            for gi in routes[r]["stops"]:
                f.write(f'    <stop busStop="{names[gi]}" duration="9999"/>\n')
            f.write("  </vehicle>\n")
        f.write("</routes>\n")
    return path


def build(seed):
    net = sumolib.net.readNet(NET)
    edges = corridor_edges(net)
    names, stop_edge, routes = route_defs(net, edges)
    files = [os.path.join(HERE, n) for n in ("stops2.add.xml", f"bg_{seed}.rou.xml", f"corr_{seed}.rou.xml", f"bus2_{seed}.rou.xml")]
    if all(os.path.exists(f) and os.path.getsize(f) > 0 for f in files):
        stops, bg, corr, bus = files
    else:
        stops = write_stops(names, stop_edge)
        bg = write_background(seed)
        corr = write_corridor_flow(edges, seed)
        bus = write_buses(routes, names, seed)
    return {"net": NET, "stops": stops, "routes": [bg, corr, bus], "edges": [e.getID() for e in edges],
            "edge_x0": [e.getFromNode().getCoord()[0] for e in edges], "stop_names": names, "lines": routes}


if __name__ == "__main__":
    print(build(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
