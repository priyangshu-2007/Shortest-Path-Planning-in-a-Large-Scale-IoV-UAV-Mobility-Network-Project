<<<<<<< HEAD
# Shortest-path planning on a large road network (Dijkstra vs A*)

Python does the preprocessing, experiment driving and analysis; C++ implements the algorithms.

## Dataset
9th DIMACS Implementation Challenge (Shortest Paths), USA road network, New York City
(264,346 nodes, 733,846 arcs). Public domain; originally US Census TIGER/Line data.
Download page: http://www.diag.uniroma1.it/challenge9/download.shtml

Put the three files in `data/` with these names:

| File in `data/` | DIMACS file |
|---|---|
| `Distance.gz`    | `USA-road-d.NY.gr.gz` (distance weights) |
| `Travel_Time.gz` | `USA-road-t.NY.gr.gz` (travel-time weights) |
| `Coordinates.gz` | `USA-road-d.NY.co.gz` (lon/lat in micro-degrees) |

## Requirements
Python 3.8+ with `matplotlib`, `numpy`, `markdown` (`pip install matplotlib numpy markdown`) and `g++` with C++17 support.

## Run everything
```
./run_all.sh
```
The project automatically resolves the correct file and directory names on case-sensitive filesystems (for example `Preprocessing.py`/`Data` instead of lowercase variants).

or step by step:
```
python3 Preprocessing.py       # Parts A,B   -> processed/ (graph files, queries, dataset_info.json)
g++ -O2 -std=c++17 -Wall -o sp Algorithms.cpp # Parts C,D -> ./sp (Dijkstra + A*)
python3 experiments.py         # Part E, bonus -> results/*.csv, *_paths.txt, run_meta.json
python3 Analysis.py            # Part F      -> results/report.html, report.md, fig_*.png, all_results.csv
```
Preprocessing takes about a minute; the experiments about a minute; analysis a few seconds.

## Files
| File | Role |
|---|---|
| `preprocess.py` | Reads the DIMACS files, merges arcs into undirected edges, checks connectivity, builds nested BFS subgraphs (1K-264K vertices), query pairs, density variants, disconnected test graph |
| `sp.cpp` | Adjacency-list graph, Dijkstra (min-priority queue), A* (scaled haversine heuristic), explicit path reconstruction, metrics, timing, dynamic weights `w = alpha*d + beta*c` |
| `experiments.py` | Compiles and runs `sp` on all sizes and weight models, density experiment, disconnected test, bonus scenarios |
| `analysis.py` | Verifies results (equal costs, valid paths), builds tables, plots, Part F answers and the single report |
| `results/report.html` / `report.md` | The complete report (Parts A-F and bonus) |
| `results/all_results.csv` | Every query: size, weights, algorithm, cost, hops, vertices explored, edges examined, time |
| `results/summary_table.csv` | Averages per size and algorithm |

## Reproducibility
All randomness uses fixed seeds (42). Costs, vertices explored and edges examined are deterministic; execution times vary slightly by machine.
Time per query is the mean per run, at least 5 runs and at least 50 ms in total. *Vertices explored* = vertices finalised (destination included); *edges examined* = adjacency entries scanned from finalised vertices.

## Command-line use of the solver
```
./sp --graph processed/graph_1000.txt --queries processed/queries_1000.txt --mode d --out out.csv --paths paths.txt --reps 5
```
`--mode d` distance, `t` travel time, `dyn` = `alpha*distance + beta*congestion` (`--alpha A --beta B --cong file`, one value per edge).
=======
# Shortest-Path-Planning-in-a-Large-Scale-IoV-UAV-Mobility-Network-Project
Compares Dijkstra and A* shortest-path algorithms on a real New York road network (264K intersections, 365K roads), testing graph size, density, unreachable routes and changing traffic congestion. Both find identical optimal routes, while A* explores only about 27–53% of the vertices, making it better for large-scale route planning.
>>>>>>> 9e1dd873c047bdd888d5eacb863e7607b94c7ad1
