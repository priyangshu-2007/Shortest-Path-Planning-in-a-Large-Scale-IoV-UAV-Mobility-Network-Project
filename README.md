# Shortest-Path Planning on a Large-Scale Road Network (Dijkstra vs A*)

Dijkstra's algorithm and A* implemented from scratch in C++ and compared on a real road network
(9th DIMACS Challenge, New York: 264,346 vertices, 365,050 undirected weighted edges).
Python handles preprocessing, experiment driving and analysis.

## Dataset
9th DIMACS Implementation Challenge (Shortest Paths), USA road network, New York City.
Public domain; originally US Census TIGER/Line data.
Download page: http://www.diag.uniroma1.it/challenge9/download.shtml

Put the three files in the `Data/` folder with these names:

| File in `Data/` | DIMACS file |
|---|---|
| `Distance.gz`    | `USA-road-d.NY.gr.gz` (distance weights) |
| `Travel_Time.gz` | `USA-road-t.NY.gr.gz` (travel-time weights) |
| `Coordinates.gz` | `USA-road-d.NY.co.gz` (longitude/latitude in micro-degrees) |

## Requirements
- Python 3.8+ with `matplotlib`, `numpy`, `markdown`: `pip install matplotlib numpy markdown`
- `g++` with C++17 support (MinGW-w64 or MSYS2 on Windows), available on the PATH

## How to run (Windows, from the project folder)
Run the three steps in this order:

```
python Preprocessing.py
python experiments.py
python Analysis.py
start results\report.html
```

- If `python` is not recognised, use `py` instead.
- `Preprocessing.py` needs to run only once (about a minute); `experiments.py` takes a few minutes; `Analysis.py` a few seconds.
- `experiments.py` compiles `Algorithms.cpp` to `Algorithms.exe` by itself.
- Linux/macOS/Git Bash users can run everything with `./run_all.sh`.

## Files
| File | Role |
|---|---|
| `Preprocessing.py` | Reads the DIMACS files, merges opposite arcs into undirected edges, checks connectivity, builds nested connected BFS subgraphs (1,000 to 264,346 vertices), query pairs, density variants and a disconnected test graph |
| `Algorithms.cpp` | Adjacency-list graph, Dijkstra (min-priority queue), A* (scaled haversine heuristic), explicit path reconstruction, metrics and timing |
| `experiments.py` | Compiles and runs the C++ program on all sizes and both weight models, the density experiment and the disconnected-pair test |
| `Analysis.py` | Verifies results (equal costs, valid paths), builds tables, plots, the Part F answers and the report |
| `results/report.html`, `results/report.md` | The complete report |
| `results/all_results.csv`, `results/summary_table.csv` | Per-query results and per-size averages |
| `results/fig_main.png`, `fig_ratio.png`, `fig_density.png` | Plots comparing the algorithms |

## Reproducibility
All randomness uses fixed seeds (42). Costs, vertices explored and edges examined are deterministic;
execution times vary slightly between machines.
Each query is repeated at least 5 times and for at least 50 ms in total, and the mean time per run is reported.
*Vertices explored* = vertices finalised (destination included); *edges examined* = adjacency entries
scanned from finalised vertices.

## Using the compiled solver directly
```
Algorithms --graph processed/graph_1000.txt --queries processed/queries_1000.txt --mode d --out out.csv --paths paths.txt --reps 5
```
`--mode d` uses distance weights and `--mode t` uses travel-time weights.
