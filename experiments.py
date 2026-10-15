#!/usr/bin/env python3
"""
experiments.py -- Part E (+ density experiment, disconnected test) driver.

Compiles Algorithms.cpp, runs it on every graph size / weight model, and stores raw outputs in results/.
Analysis.py turns those raw outputs into tables, plots and the report.
"""
import json, os, re, subprocess, sys

PROC, RES = "processed", "results"
BIN = os.path.abspath("Algorithms" + (".exe" if os.name == "nt" else ""))   # compiled C++ program
REPS = 5                       # minimum timing repetitions per query


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


def main():
    os.makedirs(RES, exist_ok=True)
    print(sh(["g++", "-O2", "-std=c++17", "-Wall", "-o", BIN, "Algorithms.cpp"]) or "compiled Algorithms.cpp")
    info = json.load(open(f"{PROC}/dataset_info.json"))
    meta = {"reps": REPS, "graph_stats": {}, "density": {}}

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

    json.dump(meta, open(f"{RES}/run_meta.json", "w"), indent=1)
    print("all experiments finished")


if __name__ == "__main__":
    sys.exit(main())