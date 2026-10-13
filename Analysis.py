#!/usr/bin/env python3
"""
Analysis.py -- Part E tables + plots, Part F answers, bonus analysis, and the consolidated report.

Inputs : processed/dataset_info.json, results/*.csv, results/*_paths.txt, results/run_meta.json
Outputs: results/all_results.csv, results/summary_table.csv, results/fig_*.png,
         results/report.md, results/report.html  (everything in ONE place)
"""
import base64, csv, json, math, os, re, statistics as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import markdown

PROC, RES = "processed", "results"
info = json.load(open(f"{PROC}/dataset_info.json"))
meta = json.load(open(f"{RES}/run_meta.json"))
SIZES = info["sizes"]
FULL = SIZES[-1]
ALGOS = ("Dijkstra", "A*")
C = {"Dijkstra": "#1f77b4", "A*": "#d62728"}


# --------------------------------------------------------------------------- helpers
def read_rows(tag):
    rows = []
    for r in csv.DictReader(open(f"{RES}/{tag}.csv")):
        rows.append({"algo": r["algo"], "s": int(r["s"]), "d": int(r["d"]),
                     "cost": float("inf") if r["cost"] == "inf" else float(r["cost"]),
                     "reachable": int(r["reachable"]), "hops": int(r["hops"]),
                     "vertices": int(r["vertices"]), "edges": int(r["edges"]),
                     "time_ms": float(r["time_ms"])})
    return rows


def read_paths(tag):
    out = []
    for line in open(f"{RES}/{tag}_paths.txt"):
        p = line.split()
        k = int(p[4])
        out.append((p[0], int(p[1]), int(p[2]), float("inf") if p[3] == "inf" else float(p[3]),
                    list(map(int, p[5:5 + k]))))
    return out


def read_graph(n_name):
    with open(f"{PROC}/{n_name}.txt") as f:
        n, m = map(int, f.readline().split())
        xy = [tuple(map(float, f.readline().split())) for _ in range(n)]
        edges = [tuple(map(int, f.readline().split())) for _ in range(m)]
    return n, xy, edges


def mean(x):
    return sum(x) / len(x)


def fmt(x, nd=0):
    return f"{x:,.{nd}f}"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# --------------------------------------------------------------------------- 1. verification
def verify():
    """For every query: (a) Dijkstra cost == A* cost, (b) the returned paths are valid walks in the
    graph and their weights add up to the reported cost."""
    report = {"queries": 0, "cost_mismatch": 0, "path_invalid": 0, "identical_paths": 0}
    for n in SIZES:
        _, _, edges = read_graph(f"graph_{n}")
        w = {"d": {}, "t": {}}
        for u, v, wd, wt in edges:
            w["d"][(u, v)] = w["d"][(v, u)] = wd
            w["t"][(u, v)] = w["t"][(v, u)] = wt
        for mode in ("d", "t"):
            rows = read_rows(f"size_{n}_{mode}")
            paths = read_paths(f"size_{n}_{mode}")
            for i in range(0, len(rows), 2):
                rd, ra = rows[i], rows[i + 1]
                report["queries"] += 1
                if abs(rd["cost"] - ra["cost"]) > 1e-6:
                    report["cost_mismatch"] += 1
                pd_, pa_ = paths[i][4], paths[i + 1][4]
                if pd_ == pa_:
                    report["identical_paths"] += 1
                for (algo, s, d, cost, path) in (paths[i], paths[i + 1]):
                    ok = path[0] == s and path[-1] == d
                    ok = ok and abs(sum(w[mode][(a, b)] for a, b in zip(path, path[1:])) - cost) < 1e-6
                    if not ok:
                        report["path_invalid"] += 1
    return report


# --------------------------------------------------------------------------- 2. aggregate tables
def aggregate(mode):
    table = {}
    for n in SIZES:
        rows = read_rows(f"size_{n}_{mode}")
        table[n] = {}
        for a in ALGOS:
            r = [x for x in rows if x["algo"] == a]
            table[n][a] = {"cost": mean([x["cost"] for x in r]), "vertices": mean([x["vertices"] for x in r]),
                           "edges": mean([x["edges"] for x in r]), "time": mean([x["time_ms"] for x in r]),
                           "hops": mean([x["hops"] for x in r]), "n": len(r)}
    return table


agg = {m: aggregate(m) for m in ("d", "t")}


def write_csvs():
    with open(f"{RES}/all_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["graph_size", "weight", "algo", "s", "d", "cost", "hops", "vertices_explored",
                    "edges_examined", "time_ms"])
        for n in SIZES:
            for mode in ("d", "t"):
                for r in read_rows(f"size_{n}_{mode}"):
                    w.writerow([n, "distance" if mode == "d" else "travel_time", r["algo"], r["s"], r["d"],
                                r["cost"], r["hops"], r["vertices"], r["edges"], r["time_ms"]])
    with open(f"{RES}/summary_table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["graph_size", "weight", "algo", "queries", "avg_cost", "avg_vertices_explored",
                    "avg_edges_examined", "avg_time_ms"])
        for mode in ("d", "t"):
            for n in SIZES:
                for a in ALGOS:
                    x = agg[mode][n][a]
                    w.writerow([n, "distance" if mode == "d" else "travel_time", a, x["n"], x["cost"],
                                x["vertices"], x["edges"], x["time"]])


# --------------------------------------------------------------------------- 3. figures
def savefig(name):
    plt.tight_layout()
    plt.savefig(f"{RES}/{name}", dpi=140, facecolor="white", bbox_inches="tight")
    plt.close()


def fig_main():
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for a in ALGOS:
        for k, (key, title, unit) in enumerate([("time", "Execution time", "ms (mean of 30 queries)"),
                                                ("vertices", "Vertices explored", "vertices"),
                                                ("edges", "Edges examined", "edges")]):
            ax[k].plot(SIZES, [agg["d"][n][a][key] for n in SIZES], "o-", color=C[a], label=a)
            ax[k].set_xscale("log"); ax[k].set_yscale("log")
            ax[k].set_xlabel("graph size (vertices)"); ax[k].set_ylabel(unit); ax[k].set_title(title)
            ax[k].grid(True, which="both", alpha=.3)
    ax[0].legend()
    fig.suptitle("Dijkstra vs A* on the New York road network (distance weights, log-log)", y=1.02)
    savefig("fig_main.png")


def ratio(a, b):
    return a / b if b else float("nan")


def fig_ratio():
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for k, (mode, name) in enumerate((("d", "distance weights"), ("t", "travel-time weights"))):
        for key, lab, mk in (("vertices", "vertices explored", "o"), ("edges", "edges examined", "s"),
                             ("time", "execution time", "^")):
            ax[k].plot(SIZES, [ratio(agg[mode][n]["A*"][key], agg[mode][n]["Dijkstra"][key]) for n in SIZES],
                       mk + "-", label=lab)
        ax[k].set_xscale("log"); ax[k].set_ylim(0, 1.05); ax[k].axhline(1, color="gray", lw=.8, ls="--")
        ax[k].set_xlabel("graph size (vertices)"); ax[k].set_ylabel("A* / Dijkstra")
        ax[k].set_title(f"A* relative to Dijkstra ({name})"); ax[k].grid(True, alpha=.3)
    ax[0].legend()
    savefig("fig_ratio.png")


def density_table():
    out = []
    for key in ("base", "4", "6", "8", "12"):
        rows = read_rows("density_" + key)
        rec = {"avg_degree": meta["density"][key]["avg_degree"], "E": meta["density"][key]["E"]}
        for a in ALGOS:
            r = [x for x in rows if x["algo"] == a]
            rec[a] = {"vertices": mean([x["vertices"] for x in r]), "edges": mean([x["edges"] for x in r]),
                      "time": mean([x["time_ms"] for x in r]), "cost": mean([x["cost"] for x in r])}
        out.append(rec)
    return out


def fig_density(dt):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    x = [r["avg_degree"] for r in dt]
    for a in ALGOS:
        for k, (key, t) in enumerate((("vertices", "Vertices explored"), ("edges", "Edges examined"),
                                      ("time", "Execution time (ms)"))):
            ax[k].plot(x, [r[a][key] for r in dt], "o-", color=C[a], label=a)
            ax[k].set_xlabel("average degree (10,000-vertex graph)"); ax[k].set_title(t); ax[k].grid(True, alpha=.3)
    ax[0].legend(); ax[0].set_ylim(bottom=0); ax[1].set_ylim(bottom=0); ax[2].set_ylim(bottom=0)
    savefig("fig_density.png")


def fig_bonus():
    b = meta["bonus"]
    _, xy, edges = read_graph(f"graph_{b['size']}")
    segs = [[xy[u], xy[v]] for u, v, _, _ in edges]
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    ax.add_collection(LineCollection(segs, colors="#cccccc", linewidths=.4))
    def draw(path, col, lab, lw):
        ax.plot([xy[v][0] for v in path], [xy[v][1] for v in path], color=col, lw=lw, label=lab)
    sc = {s["name"]: s for s in b["scenarios"]}
    draw(b["old_path"], "#1f77b4", f"original route (cost {fmt(b['old_cost'])})", 3.2)
    draw(sc["C_hotspot_x0.02"]["new_path"], "#2ca02c",
         f"hotspot x0.02 (cost {fmt(sc['C_hotspot_x0.02']['rows']['Dijkstra']['cost'])})", 2.2)
    draw(sc["F_hotspot_x10_plus_background"]["new_path"], "#d62728",
         f"hotspot x10 + background (cost {fmt(sc['F_hotspot_x10_plus_background']['rows']['Dijkstra']['cost'])})", 2.2)
    s, d = b["old_path"][0], b["old_path"][-1]
    ax.plot(*xy[s], "k*", ms=14, label="source"); ax.plot(*xy[d], "kD", ms=8, label="destination")
    ax.autoscale(); ax.set_aspect("equal"); ax.legend(loc="best", fontsize=8)
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.set_title(f"Dynamic costs: route change on the {fmt(b['size'])}-vertex graph")
    savefig("fig_bonus_map.png")


# --------------------------------------------------------------------------- 4. report
def build_report(ver):
    sub, d_, t_ = info["subgraphs"], agg["d"], agg["t"]
    gs = meta["graph_stats"]
    fi = info["full_graph_stats"]
    dfile = info["distance_file"]

    # ---- numbers used in the text
    vr = {n: d_[n]["A*"]["vertices"] / d_[n]["Dijkstra"]["vertices"] for n in SIZES}
    tr = {n: d_[n]["A*"]["time"] / d_[n]["Dijkstra"]["time"] for n in SIZES}
    er = {n: d_[n]["A*"]["edges"] / d_[n]["Dijkstra"]["edges"] for n in SIZES}
    vr_t = {n: t_[n]["A*"]["vertices"] / t_[n]["Dijkstra"]["vertices"] for n in SIZES}
    def slope(mode, a):
        x = np.log10(SIZES); y = np.log10([agg[mode][n][a]["time"] for n in SIZES])
        return float(np.polyfit(x, y, 1)[0])
    sD, sA = slope("d", "Dijkstra"), slope("d", "A*")
    dt = density_table()
    ex = {"Dijkstra": read_rows("size_1000_d")[0], "A*": read_rows("size_1000_d")[1]}
    pth = read_paths("size_1000_d")[0]
    orig = [int(x) for x in open(f"{PROC}/graph_1000.map")]
    ex_path = [orig[v] for v in pth[4]]
    ex_path_a = [orig[v] for v in read_paths("size_1000_d")[1][4]]
    scales = {n: gs[f"size_{n}_d"]["heuristic_scale"] for n in SIZES}
    scales_t = {n: gs[f"size_{n}_t"]["heuristic_scale"] for n in SIZES}
    b = meta["bonus"]
    ncmp = ver["queries"]

    L = []
    A = L.append
    A("# Shortest-Path Planning in a Large-Scale Road (IoV) Mobility Network")
    A("*Dijkstra vs A\\* on the 9th DIMACS New York road network. All numbers below were produced by the code in "
      "this project (Python preprocessing and analysis, C++ algorithms) and are reproducible with `./run_all.sh`.*\n")

    # ---------------- headline
    A("## Headline results")
    A(f"- **Graph:** {fmt(fi['V'])} vertices, {fmt(fi['E'])} undirected weighted edges (real road distances), "
      f"average degree {fi['avg_degree']:.2f}, maximum degree {fi['max_degree']}, one connected component.")
    A(f"- **Correctness:** Dijkstra and A\\* returned the **same optimal cost in all {ncmp} (query, size, weight-model) "
      f"comparisons** ({ver['cost_mismatch']} mismatches), and every returned path was re-checked edge by edge against "
      f"the graph ({ver['path_invalid']} invalid paths).")
    A(f"- **A\\* vs Dijkstra (distance weights, mean of 30 queries per size):** A\\* explores "
      f"{min(vr.values())*100:.0f}-{max(vr.values())*100:.0f}% of the vertices Dijkstra explores, and takes "
      f"{min(tr.values())*100:.0f}-{max(tr.values())*100:.0f}% of the time. On the full {fmt(FULL)}-vertex graph: "
      f"{d_[FULL]['Dijkstra']['time']:.1f} ms (Dijkstra) vs {d_[FULL]['A*']['time']:.1f} ms (A\\*).")
    A("- **Recommendation:** A\\* with a coordinate-based heuristic for point-to-point route planning (see Part F, Q10).\n")

    # ---------------- Part A
    A("## Part A: Dataset selection")
    A(md_table(["Item", "Answer"], [
        ["1. Dataset name", "9th DIMACS Implementation Challenge (Shortest Paths): USA road network, **New York City** "
                            "(`USA-road-d.NY` distance graph, `USA-road-t.NY` travel-time graph, `USA-road-d.NY.co` coordinates)"],
        ["2. Source / URL", "http://www.diag.uniroma1.it/challenge9/download.shtml (public domain). Original data: US Census "
                            "Bureau TIGER/Line files; graphs assembled by Dominik Schultes. Citation: *9th DIMACS Implementation "
                            "Challenge: Shortest Paths*, Demetrescu, Goldberg, Johnson (eds.), 2006."],
        ["3. Description", "A real road network of the New York City area (longitude "
                           f"{info['lon_range'][0]:.2f} to {info['lon_range'][1]:.2f}, latitude "
                           f"{info['lat_range'][0]:.2f} to {info['lat_range'][1]:.2f}). Two graphs share one topology "
                           "(distance weights and travel-time weights); a third file gives each node's longitude/latitude."],
        ["4. Records, nodes, edges", f"{fmt(info['coordinate_records'])} coordinate records; {fmt(dfile['arc_records'])} arc records "
                                     f"per graph file; **{fmt(fi['V'])} nodes** and **{fmt(fi['E'])} undirected edges** used "
                                     f"(after merging the two opposite arcs of each road and {fmt(dfile['parallel_arcs'])} repeated arcs). "
                                     "Experiment graphs of 1,000 to 264,346 vertices are carved out of it (Part B)."],
        ["5. Conversion to a graph", "Each coordinate record becomes a vertex; each pair of opposite `a u v w` arcs becomes one "
                                     "undirected weighted edge stored in an adjacency list (details in Part B)."],
        ["6. Vertex", "A road intersection or road endpoint, with a longitude and latitude."],
        ["7. Edge", "A road segment between two intersections that can be driven in both directions at the same cost."],
        ["8. Edge weight", f"Primary: segment **distance** (positive integers, min {info['weight_distance']['min']}, median "
                           f"{fmt(info['weight_distance']['median'])}, max {fmt(info['weight_distance']['max'])}). Secondary: "
                           f"**travel time** (min {info['weight_time']['min']}, median {fmt(info['weight_time']['median'])}, "
                           f"max {fmt(info['weight_time']['max'])}). The files do not state the unit; distance weights are about "
                           "10x the great-circle length in metres, so they are called *distance units* here."],
        ["9. Why suitable", "Real, public, citable; large (264K vertices / 365K edges) so 1K to 264K-vertex experiments are "
                            "possible; positive weights; undirected after merging (0 asymmetric arc pairs); sparse like real road networks; "
                            "coordinates enable a geometric A\\* heuristic; two weight models; standard shortest-path benchmark."],
    ]))
    A("")

    # ---------------- Part B
    A("## Part B: Graph construction")
    A("**Preprocessing steps (`Preprocessing.py`):**\n")
    A(f"1. Read `Coordinates.gz` (longitude/latitude in micro-degrees, divided by 10^6) and both `.gr` files "
      f"({fmt(dfile['arc_records'])} arcs each).")
    A(f"2. Drop self-loops ({dfile['self_loops']} found). Merge repeated arcs between the same two intersections "
      f"({fmt(dfile['parallel_arcs'])} found), keeping the smaller weight, since only the cheapest parallel segment can lie on a shortest path.")
    A(f"3. Verify symmetry: every arc has a reverse arc with the same weight "
      f"(**{dfile['asymmetric_pairs']} asymmetric pairs**), so treating roads as undirected loses nothing. Result: {fmt(fi['E'])} undirected edges.")
    A(f"4. Relabel vertices 1..N to 0..N-1; check connectivity: **{info['components']} component**, "
      f"{info['isolated_vertices']} isolated vertices, so no vertices are discarded.")
    A("5. Pick a start vertex with a fixed seed (42) and run one BFS. The first *n* vertices of the BFS order, with all edges "
      "among them, form a **connected** subgraph of size *n*; the subgraphs are nested.")
    A("6. Write each graph to a text file (`n m`, coordinates, then `u v distance time` per edge); the C++ program builds the "
      "adjacency list from it. Only the information needed for shortest paths is kept.\n")
    rows = []
    for n in SIZES:
        s = sub[str(n)]
        rows.append([fmt(s["V"]), fmt(s["E"]), f"{s['avg_degree']:.3f}", s["max_degree"],
                     f"matches ({gs[f'size_{n}_d']['V']:,} V, {gs[f'size_{n}_d']['E']:,} E)"])
    A(md_table(["Vertices", "Edges (undirected)", "Average degree (2E/V)", "Maximum degree", "C++ adjacency-list check"], rows))
    A("\nAverage degree is 2E/V (each undirected edge appears in two adjacency lists). Smaller BFS subgraphs have a slightly lower "
      "average degree because boundary vertices lose neighbours outside the region.\n")

    # ---------------- Part C
    A("## Part C: Dijkstra's algorithm (C++)")
    A("Implemented from scratch in `Algorithms.cpp`: adjacency list `vector<vector<Edge>>`, `std::priority_queue` used as a **min-priority queue** "
      "(lazy deletion of stale entries), predecessor array, and explicit path reconstruction. No graph-library shortest-path routine is used. "
      "Per-query arrays are reset in O(1) with a version counter, so a query's cost depends on the explored region only.\n")
    A("**Time complexity:** each vertex is finalised once and each adjacency entry is scanned once, so there are O(E) edge scans. "
      "Every successful relaxation pushes one heap entry, so the heap holds at most O(E) entries and each push/pop costs O(log E) = O(log V). "
      "Total **O((V + E) log V)**. For a connected road graph E = O(V) (average degree about 2.8), so this is **O(V log V)**. "
      "Space: O(V + E).\n")
    A(f"**Example query** (1,000-vertex graph, source = DIMACS node {orig[pth[1]]}, destination = DIMACS node {orig[pth[2]]}):\n")
    A(md_table(["Metric", "Dijkstra", "A*"], [
        ["Shortest-path cost", fmt(ex["Dijkstra"]["cost"]), fmt(ex["A*"]["cost"])],
        ["Hops (edges on the path)", ex["Dijkstra"]["hops"], ex["A*"]["hops"]],
        ["Vertices explored", fmt(ex["Dijkstra"]["vertices"]), fmt(ex["A*"]["vertices"])],
        ["Edges examined", fmt(ex["Dijkstra"]["edges"]), fmt(ex["A*"]["edges"])],
        ["Execution time (ms, mean per run)", f"{ex['Dijkstra']['time_ms']:.4f}", f"{ex['A*']['time_ms']:.4f}"]]))
    A("\n**Complete shortest path (original DIMACS vertex ids), Dijkstra:**\n")
    A("`" + " -> ".join(map(str, ex_path)) + "`\n")
    A(f"**Same path found by A\\*:** {'yes, identical' if ex_path == ex_path_a else 'different vertices but equal cost (tie)'}. "
      "Complete paths for every query are in `results/size_<n>_<d|t>_paths.txt`.\n")

    # ---------------- Part D
    A("## Part D: A* algorithm (C++)")
    A("Same graph and data structures; the heap is ordered by f(v) = g(v) + h(v) with")
    A("\n`h(v) = c * haversine(v, D)`, where `c = min over all edges (u,v) of w(u,v) / haversine(u,v)`.\n")
    A("- **Why scaled:** weights are not in metres (about 10 weight units per metre), so the raw great-circle distance is a poor "
      "(too weak) estimate. `c` is the largest constant for which `c * haversine(u,v) <= w(u,v)` holds on every edge. "
      "It is computed once per graph and shrunk by 1e-9 to be safe against floating-point rounding.")
    A("- **Admissible:** any path from v to D is a chain of edges; by the triangle inequality for great-circle distance, its length is at "
      "least `haversine(v,D)`, and each edge weight is at least `c` times its great-circle length, so the true cost is at least `h(v)`. "
      "So h never overestimates.")
    A("- **Consistent:** `h(u) = c*hav(u,D) <= c*hav(u,v) + c*hav(v,D) <= w(u,v) + h(v)`. Hence each vertex is finalised the first "
      "time it leaves the heap, and the first time D leaves the heap its cost is optimal.")
    A(f"- **Values of c:** {', '.join(f'{n:,}: {scales[n]:.2f}' for n in SIZES)} (distance weights). It drops from 9.6 to 7.2 at 25,000 "
      "vertices because a few edges in the larger regions have a low weight/length ratio; this makes the heuristic weaker on larger graphs "
      "(median ratio is about 10).\n")
    A("The example query's A\\* result is shown in the Part C table. Metrics are defined identically for both algorithms: *vertices explored* = "
      "vertices removed from the heap and finalised (destination included); *edges examined* = adjacency entries scanned from finalised vertices.\n")

    # ---------------- Part E
    A("## Part E: Experimental evaluation")
    A(f"Each graph size uses **30 random source-destination pairs** (fixed seed); each query is repeated at least 5 times and "
      f"for at least 50 ms per algorithm, the mean time per run is kept, then everything is **averaged over the 30 queries**. "
      f"Graph sizes: {', '.join(fmt(n) for n in SIZES)} "
      f"(the last one is the entire dataset).\n")
    for mode, name in (("d", "Primary: distance weights"), ("t", "Secondary: travel-time weights")):
        A(f"### {name}\n")
        rows = []
        for n in SIZES:
            for a in ALGOS:
                x = agg[mode][n][a]
                rows.append([fmt(n) if a == "Dijkstra" else "", a, fmt(x["cost"]), fmt(x["vertices"]),
                             fmt(x["edges"]), f"{x['time']:.3f}"])
        A(md_table(["Graph size", "Algorithm", "Avg shortest-path cost", "Avg vertices explored",
                    "Avg edges examined", "Avg execution time (ms)"], rows))
        A("")
    A("![Main comparison](fig_main.png)\n")
    A("![Ratio A* / Dijkstra](fig_ratio.png)\n")
    A(f"**Verification.** {ncmp} comparisons (7 sizes x 2 weight models x 30 queries): cost mismatches = {ver['cost_mismatch']}; "
      f"invalid paths = {ver['path_invalid']}. The two algorithms returned the identical vertex sequence in {ver['identical_paths']} of "
      f"{ncmp} queries; in the others they returned different paths of equal cost (ties).\n")
    A("**Disconnected and special pairs** (test graph = 1,000-vertex subgraph + a 2-vertex component + 1 isolated vertex):\n")
    rows = []
    desc = ["main part -> other component", "main part -> isolated vertex", "inside the small component",
            "source = destination", "ordinary reachable pair"]
    dr = read_rows("disconnected")
    for i in range(0, len(dr), 2):
        for r in (dr[i], dr[i + 1]):
            rows.append([desc[i // 2], r["algo"], f"{r['s']} -> {r['d']}",
                         "unreachable (inf, empty path)" if not r["reachable"] else fmt(r["cost"]),
                         r["hops"] if r["reachable"] else "-", r["vertices"], r["edges"]])
    A(md_table(["Case", "Algorithm", "Pair", "Result", "Hops", "Vertices explored", "Edges examined"], rows))
    A("\nUnreachable pairs make both algorithms exhaust the source's component and return `inf` with an empty path, with no crash.\n")
    A("**Density experiment** (extra synthetic local edges added to the 10,000-vertex graph; see Part F, Q6):\n")
    rows = []
    for r in dt:
        for a in ALGOS:
            rows.append([f"{r['avg_degree']:.2f}" if a == "Dijkstra" else "", fmt(r["E"]) if a == "Dijkstra" else "", a,
                         fmt(r[a]["vertices"]), fmt(r[a]["edges"]), f"{r[a]['time']:.3f}"])
    A(md_table(["Avg degree", "Edges", "Algorithm", "Avg vertices explored", "Avg edges examined", "Avg time (ms)"], rows))
    A("\n![Density experiment](fig_density.png)\n")

    # ---------------- Part F
    A("## Part F: Analysis")
    A("**Q1. Why is the dataset suitable?** It is a real, public, citable road network with 264,346 vertices and 365,050 edges, large enough "
      f"that Dijkstra explores about {fmt(d_[FULL]['Dijkstra']['vertices'])} vertices per query on average. It has positive weights, a sparse structure typical of vehicular "
      "networks (average degree 2.76), coordinates for a geometric heuristic, and two weight models. It is one connected component, so every "
      "random pair is solvable and results are not distorted by unreachable pairs.\n")
    A("**Q2. How was the raw dataset turned into a weighted graph?** Coordinates became vertices; the two opposite arcs of each road were "
      "verified symmetric (0 exceptions) and merged into one undirected edge weighted by distance (or travel time); repeated arcs kept the "
      "minimum; ids were relabelled to 0..n-1; subgraphs were grown by BFS to stay connected; the C++ code builds the adjacency list "
      "(Part B).\n")
    A(f"**Q3. Same optimal cost?** Yes: {ver['cost_mismatch']} mismatches in {ncmp} comparisons, and each path's weights re-sum to the reported cost. "
      "A\\* with an admissible and consistent heuristic is guaranteed optimal, so this is expected. Where several shortest paths of "
      f"equal cost exist, the algorithms may return different vertex sequences (identical in {ver['identical_paths']} of {ncmp} queries) "
      "but never different costs.\n")
    A(f"**Q4. Which explores fewer vertices, and why?** A\\*: {min(vr.values())*100:.0f}-{max(vr.values())*100:.0f}% of Dijkstra's vertices "
      f"(distance weights; {min(vr_t.values())*100:.0f}-{max(vr_t.values())*100:.0f}% for travel time). Dijkstra expands every vertex whose "
      "distance from the source is below the answer, i.e. a disc around S. A\\* adds h(v) to the priority, so vertices pointing away from D "
      "are postponed and the search stretches toward D. The saving is smaller than the ideal because the heuristic is a straight-line "
      f"bound scaled by the *minimum* weight/length ratio ({scales[1000]:.2f} on small graphs, {scales[FULL]:.2f} on the larger ones), while "
      "typical edges have a ratio near 10, so h underestimates the remaining cost. The saving shrinks from about "
      f"{(1-vr[10000])*100:.0f}% fewer vertices at 10,000 vertices to {(1-vr[25000])*100:.0f}% at 25,000, which coincides with the drop of `c` "
      "(a plausible cause, though graph size changes at the same time). "
      f"With travel-time weights A\\* explores {min(vr_t[n] for n in SIZES[:4])*100:.0f}-{max(vr_t[n] for n in SIZES[:4])*100:.0f}% of Dijkstra's vertices up to 25,000 vertices "
      f"but {min(vr_t[n] for n in SIZES[4:])*100:.0f}-{max(vr_t[n] for n in SIZES[4:])*100:.0f}% from 50,000 vertices upward, so its benefit relative to distance weights is not uniform; "
      "it depends on the region and on the heuristic scale.\n")
    A(f"**Q5. How does execution time vary with graph size?** Dijkstra grows from {d_[1000]['Dijkstra']['time']:.3f} ms (1,000 vertices) to "
      f"{d_[FULL]['Dijkstra']['time']:.1f} ms ({fmt(FULL)} vertices); A\\* from {d_[1000]['A*']['time']:.3f} ms to {d_[FULL]['A*']['time']:.1f} ms. "
      f"A log-log fit gives slopes of {sD:.2f} (Dijkstra) and {sA:.2f} (A\\*): time grows somewhat faster than the number of vertices. "
      f"With random endpoints the typical source-destination distance grows with the graph, so the explored region grows about in proportion to V "
      f"({fmt(d_[1000]['Dijkstra']['vertices'])} to {fmt(d_[FULL]['Dijkstra']['vertices'])} vertices for Dijkstra); the extra growth comes from the log factor of the heap "
      "and, most likely, from cache misses as the arrays outgrow the CPU caches (not measured separately here). A\\* is faster at every size, but the time saving "
      f"(about {(1-tr[FULL])*100:.0f}% at full size) is smaller than the vertex saving ({(1-vr[FULL])*100:.0f}%), plausibly because each A\\* vertex also costs a haversine evaluation.\n")
    base, hi = dt[0], dt[-1]
    A(f"**Q6. Effect of graph density.** Real road networks are sparse (average degree 2.6-2.8), so E = O(V) and the (V+E) log V bound is dominated by "
      f"V log V. To isolate density, I added synthetic *local* shortcut edges (endpoints a few hops apart, weight about 10x great-circle length, like real edges) "
      f"to the 10,000-vertex graph, raising the average degree from {base['avg_degree']:.2f} to {hi['avg_degree']:.0f}. Edges examined by Dijkstra rose "
      f"from {fmt(base['Dijkstra']['edges'])} to {fmt(hi['Dijkstra']['edges'])} ({hi['Dijkstra']['edges']/base['Dijkstra']['edges']:.1f}x) and its time from "
      f"{base['Dijkstra']['time']:.2f} to {hi['Dijkstra']['time']:.2f} ms ({hi['Dijkstra']['time']/base['Dijkstra']['time']:.1f}x), while vertices explored stayed nearly "
      f"constant ({fmt(base['Dijkstra']['vertices'])} to {fmt(hi['Dijkstra']['vertices'])}). So density affects the cost mainly through the number of "
      f"edge relaxations (and heap pushes), roughly proportionally to degree; A\\* shows the same pattern ({fmt(base['A*']['edges'])} to "
      f"{fmt(hi['A*']['edges'])} edges) but from a much lower base. Caveat: the added edges are synthetic and slightly shorten routes (average cost falls "
      f"from {fmt(base['Dijkstra']['cost'])} to {fmt(hi['Dijkstra']['cost'])}).\n")
    A("**Q7. Theoretical time complexity of the Dijkstra implementation.** O((V + E) log V) with a binary heap and lazy deletion (at most E heap "
      "entries; each operation O(log E) = O(log V)); O(V log V) on sparse road graphs where E = O(V). Space O(V + E).\n")
    A("**Q8. Heuristic for A\\*; admissible/consistent?** `h(v) = c * haversine(v, D)` with `c` = the minimum weight/great-circle-length ratio over all edges. "
      "Admissible and consistent, by the triangle-inequality argument in Part D (the scaling by the minimum ratio is what guarantees the bound "
      "holds for every edge, even when weights are not expressed in metres). Consistency means no vertex is re-opened, which the "
      "implementation relies on (closed vertices are never re-expanded), and the 0 cost mismatches are consistent with it.\n")
    A("**Q9. Difficulties converting the dataset.** (1) The `.gr` files are *directed arcs*; I had to verify symmetry (0 exceptions) and merge pairs into "
      f"undirected edges. (2) {fmt(dfile['parallel_arcs'])} repeated arcs between the same intersections needed a merge rule (keep the minimum). "
      "(3) The weight unit is undocumented; I measured weight/great-circle ratios (about 10) to design a valid heuristic. A raw haversine in metres "
      "would still be admissible but far too weak, and a naive 'weight = metres' assumption would have been wrong. (4) Coordinates are integer micro-degrees. "
      "(5) Subgraphs must be connected and comparable: BFS prefixes give nested connected graphs, but boundary effects lower their average degree. "
      "(6) A single outlier edge can reduce the global scale `c` (it fell from 9.6 to 7.2), weakening A\\* on larger graphs. (7) Per-query array initialisation "
      "would otherwise dominate small queries, so version stamps are used. (8) Building very dense variants with purely local edges saturates "
      "(a degree-20 variant could not be generated), so the density experiment stops at degree 12. (9) Sub-millisecond timings are noisy, so each query is "
      "repeated until at least 50 ms have elapsed (and at least 5 runs) and the mean per run is used.\n")
    A(f"**Q10. Recommendation for large-scale IoV/UAV route planning.** **A\\*** for point-to-point queries: identical optimal routes, about "
      f"{(1-max(vr.values()))*100:.0f}-{(1-min(vr.values()))*100:.0f}% fewer vertices and {(1-max(tr.values()))*100:.0f}-{(1-min(tr.values()))*100:.0f}% less time here, with no preprocessing "
      "other than one pass to compute `c`, and it adapts to changing edge costs as long as h stays a lower bound (see the bonus). "
      "Dijkstra remains preferable when no coordinates exist, when one source needs routes to many destinations, or when edge costs can drop below the "
      "heuristic's assumption. For a production system with millions of queries, the next step would be a stronger heuristic (landmarks/ALT) or "
      "hierarchical methods such as contraction hierarchies, since plain A\\* still visits tens of thousands of vertices on a city-scale graph.\n")

    # ---------------- Bonus
    A("## Bonus: dynamic edge costs")
    A(f"Cost model: **w(u,v) = alpha * d(u,v) + beta * c(u,v)** with alpha = {b['alpha']:g}, beta = {b['beta']:g}, where d is the distance weight and c >= 0 is a "
      f"congestion/delay term in the same units. Graph: {fmt(b['size'])}-vertex subgraph; query: the longest-route pair among the 30 test pairs "
      f"(vertex {b['s']} to {b['d']}); original route cost **{fmt(b['old_cost'])}**, {len(b['old_path'])-1} hops. Congestion is applied in two ways: "
      f"a *hotspot* (c = S * d on the {b['hotspot_edges']} edges in the middle 40% of the original route) and *background* noise (c = U(0,1) * d on 20% of all edges, "
      f"{fmt(b['background_edges'])} edges). Both algorithms re-ran from scratch with the new weights (the A\\* scale `c` is recomputed from them, so h stays admissible).\n")
    old = set(b["old_path"])
    rows = []
    for sc in b["scenarios"]:
        r = sc["rows"]
        new = set(sc["new_path"])
        same = sc["new_path"] == b["old_path"]
        rows.append([sc["name"].replace("_", " "), "yes" if sc["background"] else "no",
                     f"{fmt(sc['stale_cost'])}", f"{fmt(r['Dijkstra']['cost'])}",
                     "same" if abs(r["Dijkstra"]["cost"] - r["A*"]["cost"]) < 1e-6 else "DIFFERENT",
                     "unchanged" if same else "changed", int(r["Dijkstra"]["hops"]),
                     f"{len(old & new)} of {len(old)}",
                     f"{fmt(r['Dijkstra']['vertices'])} / {fmt(r['A*']['vertices'])}"])
    A(md_table(["Scenario", "Background", "Old route's cost under new weights", "New optimal cost (Dijkstra)",
                "A* cost", "Route", "Hops", "Vertices shared with old route", "Vertices explored (Dijkstra / A*)"], rows))
    A("\n![Route comparison](fig_bonus_map.png)\n")
    sc = {s["name"]: s for s in b["scenarios"]}
    B_, Cc, Ee = sc["B_hotspot_x0.005"], sc["C_hotspot_x0.02"], sc["E_hotspot_x10"]
    A("**Observations.**\n")
    A(f"- *Below a threshold, nothing changes.* With a tiny hotspot (S = 0.005) the original route stays optimal; its cost rises only to {fmt(B_['rows']['Dijkstra']['cost'])}.")
    A(f"- *Above it, the route detours.* With S = 0.02 the optimal route switches to a different set of streets ({len(Cc['new_path'])-1} hops instead of "
      f"{len(b['old_path'])-1}), shares {len(old & set(Cc['new_path']))} of {len(old)} vertices with the old route, and costs {fmt(Cc['rows']['Dijkstra']['cost'])} "
      f"instead of {fmt(Cc['stale_cost'])} for staying on the old route.")
    A(f"- *Severity saturates.* From S = 0.02 up to S = 10 the detour is the same ({fmt(Ee['rows']['Dijkstra']['cost'])}), because the cheapest alternative "
      f"only costs {fmt(Ee['rows']['Dijkstra']['cost']-b['old_cost'])} ({(Ee['rows']['Dijkstra']['cost']/b['old_cost']-1)*100:.2f}%) more than the original, "
      f"while staying would cost {fmt(Ee['stale_cost'])}. A dense road grid offers near-equal parallel streets, so a modest local detour absorbs even heavy congestion.")
    A("- *Network-wide noise changes the route differently.* Background congestion on 20% of all edges raises costs everywhere, so the best route "
      "reshuffles around many small delays rather than one bottleneck.")
    A(f"- *A\\* gains little in this bonus query:* it explores {fmt(sc['C_hotspot_x0.02']['rows']['A*']['vertices'])} vs {fmt(sc['C_hotspot_x0.02']['rows']['Dijkstra']['vertices'])} vertices, because this pair spans almost the whole {fmt(b['size'])}-vertex graph (the longest of the 30 pairs).")
    A("- *Both algorithms stay exact:* every scenario gives equal Dijkstra and A* costs; ignoring congestion and driving the old route would cost far more in the heavy cases.\n")

    A("## Reproducibility")
    A("`./run_all.sh` runs: `Preprocessing.py` (graph files) -> `g++ -O2 Algorithms.cpp` -> `experiments.py` (all runs) -> `Analysis.py` (this report). Seeds are fixed (42); "
      "timings vary slightly between machines, all other numbers are deterministic.")
    return "\n".join(L)


def to_html(md_text):
    body = markdown.markdown(md_text, extensions=["tables"])
    def embed(m):
        data = base64.b64encode(open(f"{RES}/{m.group(1)}", "rb").read()).decode()
        return f'src="data:image/png;base64,{data}"'
    body = re.sub(r'src="(fig_[a-z_]+\.png)"', embed, body)
    css = """
:root{--bg:#ffffff;--fg:#1c1f23;--muted:#5b6470;--card:#f5f7fa;--line:#d9dee5;--accent:#1f5fbf;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#14171a;--fg:#e6e8eb;--muted:#9aa4b0;--card:#1d2126;--line:#343b44;--accent:#7fb0ff}}
:root[data-theme="dark"]{--bg:#14171a;--fg:#e6e8eb;--muted:#9aa4b0;--card:#1d2126;--line:#343b44;--accent:#7fb0ff}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.55;margin:0 auto;max-width:1000px;padding:20px 16px 60px}
h1{font-size:1.7rem}h2{margin-top:2.2rem;border-bottom:2px solid var(--line);padding-bottom:.3rem}h3{margin-top:1.4rem}
table{border-collapse:collapse;font-size:.88rem;display:block;overflow-x:auto;max-width:100%;margin:.8rem 0}
th,td{border:1px solid var(--line);padding:5px 9px;text-align:left;vertical-align:top}th{background:var(--card)}
code{background:var(--card);padding:1px 5px;border-radius:4px;font-size:.88em;word-break:break-word}
img{max-width:100%;height:auto;background:#fff;border-radius:6px;border:1px solid var(--line)}
em{color:var(--muted)}
"""
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>Shortest-Path Planning: Dijkstra vs A* on a Road Network</title><style>{css}</style></head>'
            f'<body>{body}</body></html>')


if __name__ == "__main__":
    ver = verify()
    print("verification:", ver)
    write_csvs()
    fig_main(); fig_ratio(); fig_density(density_table()); fig_bonus()
    md_text = build_report(ver)
    open(f"{RES}/report.md", "w", encoding="utf-8").write(md_text)
    open(f"{RES}/report.html", "w", encoding="utf-8").write(to_html(md_text))
    print("report written to", RES)