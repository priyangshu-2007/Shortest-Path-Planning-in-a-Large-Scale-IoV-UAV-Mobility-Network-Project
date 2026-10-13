#!/usr/bin/env python3
"""
Preprocessing.py  --  Parts A and B (dataset + graph construction)

Reads the 9th DIMACS USA-road (New York) files
    Data/Distance.gz     (USA-road-d.NY.gr.gz  : distance weights)
    Data/Travel_Time.gz  (USA-road-t.NY.gr.gz  : travel-time weights)
    Data/Coordinates.gz  (USA-road-d.NY.co.gz  : lon/lat in micro-degrees)
and writes everything the C++ solver (Algorithms.cpp) needs into processed/:

    processed/graph_<n>.txt   graph with n vertices (BFS-grown connected subgraph)
    processed/graph_<n>.map   local id -> original DIMACS id
    processed/queries_<n>.txt source/destination pairs (local ids)
    processed/density_<k>.txt synthetic density variants of the 10,000-vertex graph
    processed/disc.txt        graph with disconnected components (+ queries_disc.txt)
    processed/dataset_info.json  statistics for the report

Graph file format (text, 0-indexed):
    n m
    lon lat                (n lines)
    u v w_distance w_time (m lines, one line per UNDIRECTED edge)

Everything is deterministic (fixed seed) so the experiments are reproducible.
"""
import gzip, json, math, os, random
from collections import deque

SEED = 42
SIZES = [1000, 5000, 10000, 25000, 50000, 100000, 264346]   # last = full graph
PAIRS_PER_SIZE = 30
DENSITY_BASE = 10000
DENSITY_TARGETS = [4, 6, 8, 12]            # target average degrees
DATA = "Data"
OUT = "processed"


# ----------------------------------------------------------------------------
def haversine(lon1, lat1, lon2, lat2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def read_coords(path):
    coords = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            if line[0] == "v":
                _, i, x, y = line.split()
                coords[int(i)] = (int(x) / 1e6, int(y) / 1e6)       # (lon, lat)
    return coords


def read_arcs(path):
    """Returns the raw arc list [(u, v, w), ...] exactly as stored in the file."""
    arcs = []
    with gzip.open(path, "rt") as f:
        for line in f:
            if line[0] == "a":
                _, u, v, w = line.split()
                arcs.append((int(u), int(v), int(w)))
    return arcs


def arcs_to_undirected(arcs):
    """DIMACS stores every road as two opposite arcs. Merge them into undirected edges.
    If the same pair appears more than once (parallel road segments) keep the smallest weight:
    only the cheapest one can ever be on a shortest path."""
    info = {"arc_records": len(arcs), "self_loops": 0, "parallel_arcs": 0}
    directed = {}
    for u, v, w in arcs:
        if u == v:
            info["self_loops"] += 1
            continue
        if (u, v) in directed:
            info["parallel_arcs"] += 1
            directed[(u, v)] = min(directed[(u, v)], w)
        else:
            directed[(u, v)] = w
    info["asymmetric_pairs"] = sum(1 for (u, v), w in directed.items()
                                   if directed.get((v, u)) != w)
    und = {}
    for (u, v), w in directed.items():
        key = (u, v) if u < v else (v, u)
        und[key] = min(und.get(key, 10 ** 18), w)
    info["undirected_edges"] = len(und)
    return und, info


def degree_stats(n, edges):
    deg = [0] * n
    for u, v, *_ in edges:
        deg[u] += 1
        deg[v] += 1
    return {"V": n, "E": len(edges), "avg_degree": round(2 * len(edges) / n, 4),
            "max_degree": max(deg)}


def write_graph(path, coords, edges):
    with open(path, "w") as f:
        f.write(f"{len(coords)} {len(edges)}\n")
        for lon, lat in coords:
            f.write(f"{lon:.6f} {lat:.6f}\n")
        for u, v, wd, wt in edges:
            f.write(f"{u} {v} {wd} {wt}\n")


def write_queries(path, pairs):
    with open(path, "w") as f:
        for s, d in pairs:
            f.write(f"{s} {d}\n")


# ----------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    info = {"seed": SEED}

    # ---- 1. read raw files -------------------------------------------------
    coords = read_coords(f"{DATA}/Coordinates.gz")
    arcs_d = read_arcs(f"{DATA}/Distance.gz")
    arcs_t = read_arcs(f"{DATA}/Travel_Time.gz")
    N = len(coords)
    info["coordinate_records"] = N
    info["lon_range"] = [min(c[0] for c in coords.values()), max(c[0] for c in coords.values())]
    info["lat_range"] = [min(c[1] for c in coords.values()), max(c[1] for c in coords.values())]

    und_d, info_d = arcs_to_undirected(arcs_d)
    und_t, info_t = arcs_to_undirected(arcs_t)
    info["distance_file"] = info_d
    info["time_file"] = info_t
    assert set(und_d) == set(und_t), "distance and travel-time graphs must have the same topology"

    # ---- 2. relabel 1..N -> 0..N-1, build deterministic edge list ----------
    all_edges = sorted((u - 1, v - 1, und_d[(u, v)], und_t[(u, v)]) for (u, v) in und_d)
    wd = [e[2] for e in all_edges]
    wt = [e[3] for e in all_edges]
    info["weight_distance"] = {"min": min(wd), "max": max(wd), "mean": sum(wd) / len(wd),
                               "median": sorted(wd)[len(wd) // 2]}
    info["weight_time"] = {"min": min(wt), "max": max(wt), "mean": sum(wt) / len(wt),
                           "median": sorted(wt)[len(wt) // 2]}
    lonlat = [coords[i + 1] for i in range(N)]

    adj = [[] for _ in range(N)]
    for u, v, _, _ in all_edges:
        adj[u].append(v)
        adj[v].append(u)

    # ---- 3. connectivity ---------------------------------------------------
    comp = [-1] * N
    sizes = []
    for s in range(N):
        if comp[s] != -1:
            continue
        comp[s] = len(sizes)
        q, cnt = deque([s]), 1
        while q:
            x = q.popleft()
            for y in adj[x]:
                if comp[y] == -1:
                    comp[y] = len(sizes)
                    q.append(y)
                    cnt += 1
        sizes.append(cnt)
    info["components"] = len(sizes)
    info["largest_component"] = max(sizes)
    info["isolated_vertices"] = sum(1 for a in adj if not a)
    info["full_graph_stats"] = degree_stats(N, all_edges)
    assert len(sizes) == 1, "expected one connected component; take the largest otherwise"

    # ---- 4. nested connected subgraphs via ONE BFS order -------------------
    rng = random.Random(SEED)
    start = rng.randrange(N)
    info["bfs_start_vertex_original_id"] = start + 1
    order, seen, q = [start], {start}, deque([start])
    while q:
        x = q.popleft()
        for y in adj[x]:
            if y not in seen:
                seen.add(y)
                order.append(y)
                q.append(y)
    assert len(order) == N
    pos = [0] * N
    for i, v in enumerate(order):
        pos[v] = i
    # an edge belongs to the first-n subgraph iff both endpoints have pos < n
    by_emax = sorted(all_edges, key=lambda e: max(pos[e[0]], pos[e[1]]))
    emax = [max(pos[e[0]], pos[e[1]]) for e in by_emax]

    info["subgraphs"] = {}
    import bisect
    for n in SIZES:
        k = bisect.bisect_left(emax, n)              # edges with emax < n
        edges = [(pos[u], pos[v], a, b) for u, v, a, b in by_emax[:k]]
        write_graph(f"{OUT}/graph_{n}.txt", [lonlat[order[i]] for i in range(n)], edges)
        with open(f"{OUT}/graph_{n}.map", "w") as f:
            for i in range(n):
                f.write(f"{order[i] + 1}\n")          # original 1-based DIMACS id
        r = random.Random(SEED * 1000 + n)
        pairs = []
        while len(pairs) < PAIRS_PER_SIZE:
            s, d = r.randrange(n), r.randrange(n)
            if s != d:
                pairs.append((s, d))
        write_queries(f"{OUT}/queries_{n}.txt", pairs)
        info["subgraphs"][str(n)] = degree_stats(n, edges)
        print("wrote graph", n, info["subgraphs"][str(n)])

    # ---- 5. density experiment (synthetic extra LOCAL edges) ---------------
    nb = DENSITY_BASE
    kb = bisect.bisect_left(emax, nb)
    base_edges = [(pos[u], pos[v], a, b) for u, v, a, b in by_emax[:kb]]
    base_xy = [lonlat[order[i]] for i in range(nb)]
    nbr = [[] for _ in range(nb)]
    present = set()
    for u, v, _, _ in base_edges:
        nbr[u].append(v)
        nbr[v].append(u)
        present.add((min(u, v), max(u, v)))
    base_avg = 2 * len(base_edges) / nb
    info["density_variants"] = {}
    for target in DENSITY_TARGETS:
        r = random.Random(SEED + target)
        extra = int(math.ceil((target - base_avg) * nb / 2))
        edges = list(base_edges)
        have = set(present)
        added, attempts = 0, 0
        while added < extra:
            attempts += 1
            assert attempts < 50 * extra + 1000, "cannot place enough local edges"
            u = r.randrange(nb)
            v = u
            for _ in range(r.randint(2, 12)):          # random walk of 2-12 steps (local)
                v = r.choice(nbr[v]) if nbr[v] else v
            key = (min(u, v), max(u, v))
            if u == v or key in have:
                continue
            have.add(key)
            hv = haversine(*base_xy[u], *base_xy[v])
            w_d = max(1, int(round(hv * r.uniform(9.5, 11.0))))   # same scale as real data
            edges.append((key[0], key[1], w_d, int(round(w_d * 2.5))))
            added += 1
        write_graph(f"{OUT}/density_{target}.txt", base_xy, edges)
        info["density_variants"][str(target)] = degree_stats(nb, edges)
        print("wrote density", target, info["density_variants"][str(target)])

    # ---- 6. disconnected test graph ---------------------------------------
    n0 = 1000
    k0 = bisect.bisect_left(emax, n0)
    e0 = [(pos[u], pos[v], a, b) for u, v, a, b in by_emax[:k0]]
    xy = [lonlat[order[i]] for i in range(n0)]
    lon0, lat0 = xy[0]
    xy += [(lon0 + 0.0005, lat0), (lon0 + 0.0006, lat0), (lon0 + 0.0007, lat0)]
    e0.append((n0, n0 + 1, 100, 250))                  # tiny separate component {n0, n0+1}
    # vertex n0+2 stays isolated
    write_graph(f"{OUT}/disc.txt", xy, e0)
    write_queries(f"{OUT}/queries_disc.txt",
                  [(0, n0),          # main part  -> other component   : unreachable
                   (0, n0 + 2),      # main part  -> isolated vertex   : unreachable
                   (n0, n0 + 1),     # inside the tiny component       : reachable
                   (7, 7),           # source == destination           : cost 0
                   (3, 500)])        # ordinary reachable pair
    info["disconnected_test"] = {"vertices": n0 + 3, "edges": len(e0),
                                 "note": "1000-vertex subgraph + 2-vertex component + 1 isolated vertex"}

    info["sizes"] = SIZES
    info["pairs_per_size"] = PAIRS_PER_SIZE
    with open(f"{OUT}/dataset_info.json", "w") as f:
        json.dump(info, f, indent=2)
    print("preprocessing done ->", OUT)


if __name__ == "__main__":
    main()