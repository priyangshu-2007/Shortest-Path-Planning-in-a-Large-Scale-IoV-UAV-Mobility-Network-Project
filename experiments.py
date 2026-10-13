#!/usr/bin/env python3
"""
experiments.py -- Part E (+ density experiment, disconnected test, bonus) driver.

Compiles Algorithms.cpp, runs it on every graph size / weight model, and stores raw outputs in results/.
Analysis.py turns those raw outputs into tables, plots and the report.
"""
import csv, json, os, random, re, subprocess, sys

PROC, RES = "processed", "results"
BIN = os.path.abspath("Algorithms" + (".exe" if os.name == "nt" else ""))   # compiled C++ program
SEED = 42
REPS = 5                       # timing repetitions per query (median is reported)
BONUS_SIZE = 25000


def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def run_sp(graph, queries, mode, tag, extra=None):
    out, paths = f"{RES}/{tag}.csv", f"{RES}/{tag}_paths.txt"
    cmd = [BIN, "--graph", graph, "--queries", queries, "--mode", mode,
           "--out", out, "--paths", paths, "--reps", str(REPS)] + (extra or [])
    text = sh(cmd)
    m = re.search(r"STATS V=(\d+) E=(\d+) avg_degree=([\d.]+) max_degree=(\d+) "
                  r"build_ms=([\d.]+) heuristic_scale=([\d.]+)", text)
    return {"V": int(m[1]), "E": int(m[2]), "avg_degree": float(m[3]), "max_degree": int(m[4]),
            "build_ms": float(m[5]), "heuristic_scale": float(m[6])}


def read_graph_edges(path):
    with open(path) as f:
        n, m = map(int, f.readline().split())
        for _ in range(n):
            f.readline()
        return n, [tuple(map(int, f.readline().split())) for _ in range(m)]   # (u, v, wd, wt)


def read_paths(path):
    out = []
    with open(path) as f:
        for line in f:
            p = line.split()
            algo, s, d, cost, k = p[0], int(p[1]), int(p[2]), p[3], int(p[4])
            out.append({"algo": algo, "s": s, "d": d,
                        "cost": float("inf") if cost == "inf" else float(cost),
                        "path": list(map(int, p[5:5 + k]))})
    return out


def main():
    os.makedirs(RES, exist_ok=True)
    print(sh(["g++", "-O2", "-std=c++17", "-Wall", "-o", BIN, "Algorithms.cpp"]) or "compiled Algorithms.cpp")
    info = json.load(open(f"{PROC}/dataset_info.json"))
    meta = {"reps": REPS, "graph_stats": {}, "density": {}, "bonus": {}}

    # ---------------- Part E: all sizes x both weight models ----------------
    for n in info["sizes"]:
        for mode in ("d", "t"):
            tag = f"size_{n}_{mode}"
            meta["graph_stats"][tag] = run_sp(f"{PROC}/graph_{n}.txt", f"{PROC}/queries_{n}.txt", mode, tag)
            print("done", tag, meta["graph_stats"][tag]["heuristic_scale"])

    # ---------------- disconnected / special pairs --------------------------
    meta["disc"] = run_sp(f"{PROC}/disc.txt", f"{PROC}/queries_disc.txt", "d", "disconnected")

    # ---------------- density experiment (10,000 vertices) -------------------
    q10 = f"{PROC}/queries_10000.txt"
    meta["density"]["base"] = run_sp(f"{PROC}/graph_10000.txt", q10, "d", "density_base")
    for k in (4, 6, 8, 12):
        meta["density"][str(k)] = run_sp(f"{PROC}/density_{k}.txt", q10, "d", f"density_{k}")

    # ---------------- bonus: dynamic edge costs ------------------------------
    n = BONUS_SIZE
    gpath = f"{PROC}/graph_{n}.txt"
    _, edges = read_graph_edges(gpath)
    eidx = {(min(u, v), max(u, v)): k for k, (u, v, _, _) in enumerate(edges)}
    base_rows = [r for r in csv.DictReader(open(f"{RES}/size_{n}_d.csv")) if r["algo"] == "Dijkstra"]
    pick = max(base_rows, key=lambda r: int(r["hops"]))          # longest route -> most interesting detour
    s, d = int(pick["s"]), int(pick["d"])
    with open(f"{PROC}/queries_bonus.txt", "w") as f:
        f.write(f"{s} {d}\n")
    old = [p for p in read_paths(f"{RES}/size_{n}_d_paths.txt") if p["algo"] == "Dijkstra" and p["s"] == s and p["d"] == d][0]
    old_path = old["path"]
    old_edges = [eidx[(min(a, b), max(a, b))] for a, b in zip(old_path, old_path[1:])]
    lo, hi = int(0.3 * len(old_edges)), int(0.7 * len(old_edges))
    hotspot = set(old_edges[lo:hi])                               # congested stretch in the middle of the route

    rng = random.Random(SEED)
    background = {k: rng.uniform(0.0, 1.0) for k in range(len(edges)) if rng.random() < 0.20}   # 20 % of edges
    # (name, hotspot factor S, add 20 % background congestion?)
    scenarios = [("A_background_only", 0.0, True),
                 ("B_hotspot_x0.005", 0.005, False), ("C_hotspot_x0.02", 0.02, False),
                 ("D_hotspot_x0.5", 0.5, False), ("E_hotspot_x10", 10.0, False),
                 ("F_hotspot_x10_plus_background", 10.0, True)]
    alpha, beta = 1.0, 1.0
    meta["bonus"] = {"size": n, "s": s, "d": d, "alpha": alpha, "beta": beta,
                     "old_cost": old["cost"], "old_path": old_path,
                     "hotspot_edges": len(hotspot), "background_edges": len(background), "scenarios": []}
    for name, S, use_bg in scenarios:
        c = [0.0] * len(edges)
        if use_bg:
            for k, f in background.items():
                c[k] = f * edges[k][2]                            # c = U(0,1) * d on 20 % of edges
        for k in hotspot:
            c[k] += S * edges[k][2]                               # extra congestion c = S * d on the hotspot
        cpath = f"{PROC}/cong_{name}.txt"
        with open(cpath, "w") as f:
            f.write("\n".join(f"{x:.6f}" for x in c) + "\n")
        tag = f"bonus_{name}"
        run_sp(gpath, f"{PROC}/queries_bonus.txt", "dyn", tag,
               ["--alpha", str(alpha), "--beta", str(beta), "--cong", cpath])
        rows = list(csv.DictReader(open(f"{RES}/{tag}.csv")))
        paths = read_paths(f"{RES}/{tag}_paths.txt")
        newp = [p for p in paths if p["algo"] == "Dijkstra"][0]["path"]
        stale = sum(alpha * edges[k][2] + beta * c[k] for k in old_edges)      # old route under new conditions
        meta["bonus"]["scenarios"].append({
            "name": name, "hotspot_factor": S, "background": use_bg, "new_path": newp,
            "stale_cost": stale,
            "rows": {r["algo"]: {k: (float(v) if k not in ("algo",) and v not in ("inf",) else v)
                                 for k, v in r.items() if k != "algo"} for r in rows}})
        print("bonus", name, [r["cost"] for r in rows])

    json.dump(meta, open(f"{RES}/run_meta.json", "w"), indent=1)
    print("all experiments finished")


if __name__ == "__main__":
    sys.exit(main())