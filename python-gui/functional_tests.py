import json
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vit_smart_shuttle_gui as g


def fresh():
    root = tk.Tk()
    app = g.ShuttleGUI(root)
    root.update()
    return root, app


def log_lines(app):
    return app.text.get("1.0", "end").splitlines()


out = {}
root, app = fresh()
attempts = g.MAX_PASSENGERS + 1
for _ in range(attempts):
    app.entry()
    root.update()
denied = [l for l in log_lines(app) if l.startswith("[ENTRY DENIED]")]
out["bus_full"] = {"attempts": attempts, "accepted": len(app.people), "count_label": app.passengers_var.get(),
                   "free_seats_label": app.free.get(), "denied_lines": denied,
                   "pass": len(app.people) == g.MAX_PASSENGERS and len(denied) == 1}
root.destroy()

root, app = fresh()
app.gps.set(0)
root.update()
app.update_gps()
app.update_seat()
app.refresh_people()
out["idle"] = {"route": app.route.get(), "seat": app.seat.get(), "riders": app.passengers_var.get(), "free": app.free.get(),
               "pass": app.route.get() == "0%" and app.seat.get() == "EMPTY" and app.passengers_var.get() == f"0 / {g.MAX_PASSENGERS}"}
root.destroy()

root, app = fresh()
t0 = time.perf_counter()
for _ in range(15):
    app.entry()
    app.exit()
t1 = time.perf_counter()
root.update()
out["rapid"] = {"cycles": 15, "total_s": t1 - t0, "per_cycle_ms": (t1 - t0) / 15 * 1000, "riders_after": len(app.people),
                "pass": len(app.people) == 0}
root.destroy()
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simulation", "results", "functional_tests.json"), "w"), indent=1)
