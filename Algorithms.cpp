// Algorithms.cpp  --  Parts C and D: Dijkstra and A* on a weighted undirected graph.
//
// Build :  g++ -O2 -std=c++17 -o Algorithms Algorithms.cpp
// Run   :  ./Algorithms --graph processed/graph_1000.txt --queries processed/queries_1000.txt
//               --mode d --out results/out.csv --paths results/out_paths.txt [--reps 5]
//          --mode d    : weight = distance
//          --mode t    : weight = travel time
//
// No graph library / built-in shortest-path routine is used: the graph is a plain
// adjacency list (vector<vector<Edge>>), Dijkstra uses std::priority_queue as a min-heap,
// and paths are reconstructed explicitly from predecessor pointers.
//
// Metrics (identical definition for both algorithms):
//   vertices explored = number of distinct vertices removed from the heap and finalised
//                       (the destination counts, the search stops right after it)
//   edges examined    = number of adjacency-list entries scanned from finalised vertices
//   time              = mean per run over at least --reps runs and at least 50 ms in total
//                       (path reconstruction included)

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <string>
#include <vector>
using namespace std;

static const double INF = numeric_limits<double>::infinity();
static const double EARTH_R = 6371000.0;
static const double PI = 3.14159265358979323846;
static const double MIN_TOTAL_MS = 50.0;

struct Edge { int to; double w; };

struct Graph {
    int n = 0;
    long long m = 0;                           // undirected edges
    vector<double> lonRad, latRad, cosLat;     // coordinates for the A* heuristic
    vector<int> eu, ev;                        // original edge list (file order)
    vector<double> wd, wt;                     // distance / time weights per edge
    vector<vector<Edge>> adj;                  // adjacency list (both directions stored)
};

// ---------------------------------------------------------------- graph I/O
static bool loadGraph(const string& path, Graph& G) {
    ifstream in(path);
    if (!in) return false;
    in >> G.n >> G.m;
    G.lonRad.resize(G.n); G.latRad.resize(G.n); G.cosLat.resize(G.n);
    for (int i = 0; i < G.n; i++) {
        double lon, lat;
        in >> lon >> lat;
        G.lonRad[i] = lon * PI / 180.0;
        G.latRad[i] = lat * PI / 180.0;
        G.cosLat[i] = cos(G.latRad[i]);
    }
    G.eu.resize(G.m); G.ev.resize(G.m); G.wd.resize(G.m); G.wt.resize(G.m);
    for (long long k = 0; k < G.m; k++) in >> G.eu[k] >> G.ev[k] >> G.wd[k] >> G.wt[k];
    return (bool)in;
}

static void buildAdjacency(Graph& G, const vector<double>& w) {
    G.adj.assign(G.n, {});
    for (long long k = 0; k < G.m; k++) {
        G.adj[G.eu[k]].push_back({G.ev[k], w[k]});
        G.adj[G.ev[k]].push_back({G.eu[k], w[k]});
    }
}

// ---------------------------------------------------------------- heuristic
static inline double haversine(const Graph& G, int a, int b) {
    double dphi = G.latRad[b] - G.latRad[a];
    double dlam = G.lonRad[b] - G.lonRad[a];
    double s1 = sin(dphi / 2), s2 = sin(dlam / 2);
    double h = s1 * s1 + G.cosLat[a] * G.cosLat[b] * s2 * s2;
    if (h > 1.0) h = 1.0;
    return 2.0 * EARTH_R * asin(sqrt(h));
}

// Largest c such that c * haversine(u,v) <= w(u,v) for EVERY edge.
// h(v) = c * haversine(v, D) is then admissible and consistent (see report, Part F).
// (shrunk by 1e-9 to protect against floating-point rounding)
static double heuristicScale(const Graph& G, const vector<double>& w) {
    double c = INF;
    for (long long k = 0; k < G.m; k++) {
        double g = haversine(G, G.eu[k], G.ev[k]);
        if (g > 0) c = min(c, w[k] / g);
    }
    if (c == INF) return 0.0;
    return c * (1.0 - 1e-9);
}

// ---------------------------------------------------------------- search
struct Result {
    bool found = false;
    double cost = INF;
    long long vertices = 0, edges = 0;
    vector<int> path;
};

// Per-query state is reset in O(1) with a version counter, so the cost of a query depends
// on the part of the graph it explores and not on the total graph size.
struct Work {
    vector<double> g;
    vector<int> prev, seen, closed;
    int cur = 0;
    explicit Work(int n) : g(n), prev(n), seen(n, 0), closed(n, 0) {}
};

static void reconstruct(const Work& W, int s, int d, vector<int>& path) {
    path.clear();
    for (int u = d; u != -1; u = W.prev[u]) path.push_back(u);
    reverse(path.begin(), path.end());
    // path.front() == s by construction
    (void)s;
}

typedef pair<double, int> PQItem;   // (priority, vertex)

static Result dijkstra(const Graph& G, Work& W, int s, int d) {
    Result r;
    int cur = ++W.cur;
    priority_queue<PQItem, vector<PQItem>, greater<PQItem>> pq;   // min-priority queue
    W.seen[s] = cur; W.g[s] = 0.0; W.prev[s] = -1;
    pq.push({0.0, s});
    while (!pq.empty()) {
        PQItem top = pq.top(); pq.pop();
        int u = top.second;
        if (W.closed[u] == cur) continue;          // stale heap entry
        W.closed[u] = cur;
        r.vertices++;
        if (u == d) { r.found = true; r.cost = W.g[u]; break; }
        double gu = W.g[u];
        for (const Edge& e : G.adj[u]) {
            r.edges++;
            if (W.closed[e.to] == cur) continue;
            double ng = gu + e.w;
            if (W.seen[e.to] != cur || ng < W.g[e.to]) {
                W.seen[e.to] = cur; W.g[e.to] = ng; W.prev[e.to] = u;
                pq.push({ng, e.to});
            }
        }
    }
    if (r.found) reconstruct(W, s, d, r.path);
    return r;
}

static Result astar(const Graph& G, Work& W, int s, int d, double scale) {
    Result r;
    int cur = ++W.cur;
    priority_queue<PQItem, vector<PQItem>, greater<PQItem>> pq;   // ordered by f = g + h
    W.seen[s] = cur; W.g[s] = 0.0; W.prev[s] = -1;
    pq.push({scale * haversine(G, s, d), s});
    while (!pq.empty()) {
        PQItem top = pq.top(); pq.pop();
        int u = top.second;
        if (W.closed[u] == cur) continue;
        W.closed[u] = cur;
        r.vertices++;
        if (u == d) { r.found = true; r.cost = W.g[u]; break; }
        double gu = W.g[u];
        for (const Edge& e : G.adj[u]) {
            r.edges++;
            if (W.closed[e.to] == cur) continue;
            double ng = gu + e.w;
            if (W.seen[e.to] != cur || ng < W.g[e.to]) {
                W.seen[e.to] = cur; W.g[e.to] = ng; W.prev[e.to] = u;
                pq.push({ng + scale * haversine(G, e.to, d), e.to});
            }
        }
    }
    if (r.found) reconstruct(W, s, d, r.path);
    return r;
}

// ---------------------------------------------------------------- main
int main(int argc, char** argv) {
    string graphPath, queryPath, mode = "d", outCsv = "out.csv", outPaths = "paths.txt";
    int reps = 5;
    for (int i = 1; i + 1 < argc; i += 2) {
        string k = argv[i], v = argv[i + 1];
        if (k == "--graph") graphPath = v;
        else if (k == "--queries") queryPath = v;
        else if (k == "--mode") mode = v;
        else if (k == "--out") outCsv = v;
        else if (k == "--paths") outPaths = v;
        else if (k == "--reps") reps = atoi(v.c_str());
        else { cerr << "unknown option " << k << "\n"; return 1; }
    }
    Graph G;
    if (!loadGraph(graphPath, G)) { cerr << "cannot read graph " << graphPath << "\n"; return 1; }

    // ---- choose the edge-weight model
    vector<double> w(G.m);
    if (mode == "d") w = G.wd;
    else if (mode == "t") w = G.wt;
    else { cerr << "bad mode\n"; return 1; }

    // ---- Part B: build adjacency list and report its statistics
    auto t0 = chrono::steady_clock::now();
    buildAdjacency(G, w);
    double buildMs = chrono::duration<double, milli>(chrono::steady_clock::now() - t0).count();
    long long arcs = 0; int maxDeg = 0;
    for (int u = 0; u < G.n; u++) { arcs += G.adj[u].size(); maxDeg = max<int>(maxDeg, G.adj[u].size()); }
    double scale = heuristicScale(G, w);
    printf("STATS V=%d E=%lld avg_degree=%.4f max_degree=%d build_ms=%.2f heuristic_scale=%.6f\n",
           G.n, arcs / 2, (double)arcs / G.n, maxDeg, buildMs, scale);

    // ---- read the queries
    vector<pair<int,int>> queries;
    { ifstream qin(queryPath); int s, d; while (qin >> s >> d) queries.push_back({s, d}); }

    ofstream csv(outCsv), pf(outPaths);
    csv << "algo,s,d,cost,reachable,hops,vertices,edges,time_ms\n";
    csv.precision(12); pf.precision(12);
    Work W(G.n);

    for (auto& q : queries) {
        int s = q.first, d = q.second;
        for (int a = 0; a < 2; a++) {
            const char* name = a == 0 ? "Dijkstra" : "A*";
            Result r;
            int runs = 0;
            double elapsedMs = 0.0;
            auto ts = chrono::steady_clock::now();
            do {
                r = (a == 0) ? dijkstra(G, W, s, d) : astar(G, W, s, d, scale);
                runs++;
                elapsedMs = chrono::duration<double, milli>(chrono::steady_clock::now() - ts).count();
            } while (runs < reps || elapsedMs < MIN_TOTAL_MS);
            double timeMs = elapsedMs / runs;
            csv << name << "," << s << "," << d << ",";
            if (r.found) csv << r.cost; else csv << "inf";
            csv << "," << (r.found ? 1 : 0) << "," << (r.found ? (int)r.path.size() - 1 : -1)
                << "," << r.vertices << "," << r.edges << "," << timeMs << "\n";
            pf << name << " " << s << " " << d << " ";
            if (r.found) { pf << r.cost << " " << r.path.size(); for (int v : r.path) pf << " " << v; }
            else pf << "inf 0";
            pf << "\n";
        }
    }
    return 0;
}