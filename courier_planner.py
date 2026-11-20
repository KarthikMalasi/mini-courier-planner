"""
Mini-Courier Planner
Course : Design & Analysis of Algorithms (ETCCDA302)
---------------------------------------------------------------
What this program does (in simple words):
  1. Reads a list of parcels and a map of the city.
  2. SORTS the parcels by deadline (Merge Sort).
  3. Chooses the best parcels that fit in the van (0/1 KNAPSACK, Dynamic Programming).
  4. Finds shortest paths between places (DIJKSTRA).
  5. Builds one delivery route that visits every stop (NEAREST NEIGHBOR, TSP approximation).
  6. Tests speed with small and large inputs and draws a runtime chart.

Run it with:   python courier_planner.py
"""

import csv
import heapq          # a ready-made "priority queue", used inside Dijkstra
import random
import time

DEPOT = "A"           # the courier starts and ends here
VAN_CAPACITY = 25     # the van can carry at most 25 kg


# =====================================================================
# PHASE 1: DATA DESIGN  (reading the files)
# =====================================================================
# A parcel is stored as a dictionary, for example:
#   {"id": "P1", "dest": "B", "weight": 5, "priority": 9, "deadline": 1}
# The map is stored as an "adjacency list" (a dictionary of dictionaries):
#   graph["A"] = {"B": 4, "C": 2}   means A--B is 4 km and A--C is 2 km


def load_parcels(filename):
    parcels = []
    with open(filename) as f:
        for row in csv.DictReader(f):
            parcels.append({
                "id": row["parcel_id"],
                "dest": row["destination"],
                "weight": int(row["weight_kg"]),
                "priority": int(row["priority"]),
                "deadline": int(row["deadline_days"]),
            })
    return parcels


def load_graph(filename):
    graph = {}
    with open(filename) as f:
        for row in csv.DictReader(f):
            a, b, d = row["from"], row["to"], int(row["distance_km"])
            graph.setdefault(a, {})[b] = d   # roads work both ways,
            graph.setdefault(b, {})[a] = d   # so we add both directions
    return graph


# =====================================================================
# PHASE 2A: SORTING  (Merge Sort - always O(n log n))
# =====================================================================
# Parcels with an EARLIER deadline come first.
# If two parcels have the same deadline, the HIGHER priority comes first.


def goes_before(p1, p2):
    """Return True if parcel p1 should be delivered before parcel p2."""
    if p1["deadline"] != p2["deadline"]:
        return p1["deadline"] < p2["deadline"]
    return p1["priority"] > p2["priority"]


def merge_sort(parcels):
    if len(parcels) <= 1:                 # a list of 0 or 1 item is already sorted
        return parcels
    mid = len(parcels) // 2
    left = merge_sort(parcels[:mid])      # sort the left half
    right = merge_sort(parcels[mid:])     # sort the right half
    return merge(left, right)             # join the two sorted halves


def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        # Take from the right ONLY if it must go first; on a tie keep the
        # left one (this keeps equal parcels in their original order = "stable")
        if goes_before(right[j], left[i]):
            result.append(right[j]); j += 1
        else:
            result.append(left[i]); i += 1
    result.extend(left[i:])               # add whatever is left over
    result.extend(right[j:])
    return result


def bubble_sort(parcels):
    """Slow sort O(n^2). Only used to COMPARE speed against merge sort."""
    items = parcels[:]
    n = len(items)
    for i in range(n):
        for j in range(n - i - 1):
            if goes_before(items[j + 1], items[j]):
                items[j], items[j + 1] = items[j + 1], items[j]
    return items


# =====================================================================
# PHASE 2B: DYNAMIC PROGRAMMING  (0/1 Knapsack)
# =====================================================================
# Goal: pick parcels so total weight <= van capacity and total priority
# (value) is as big as possible. Each parcel is taken fully or not at all.
#
# table[i][w] = best total priority using the first i parcels
#               when the van can carry w kg.


def knapsack(parcels, capacity):
    n = len(parcels)
    table = [[0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        weight = parcels[i - 1]["weight"]
        value = parcels[i - 1]["priority"]
        for w in range(capacity + 1):
            table[i][w] = table[i - 1][w]            # option 1: skip this parcel
            if weight <= w:                          # option 2: take it (if it fits)
                take = table[i - 1][w - weight] + value
                if take > table[i][w]:
                    table[i][w] = take

    # Walk backwards through the table to find WHICH parcels were chosen
    chosen = []
    w = capacity
    for i in range(n, 0, -1):
        if table[i][w] != table[i - 1][w]:           # value changed -> parcel i was taken
            chosen.append(parcels[i - 1])
            w -= parcels[i - 1]["weight"]
    chosen.reverse()
    return table[n][capacity], chosen, table


# =====================================================================
# PHASE 3A: DIJKSTRA'S ALGORITHM  (shortest path from one place)
# =====================================================================


def dijkstra(graph, start):
    dist = {node: float("inf") for node in graph}    # start by assuming "very far"
    previous = {node: None for node in graph}        # remembers the path
    dist[start] = 0
    queue = [(0, start)]                             # (distance, place)

    while queue:
        d, node = heapq.heappop(queue)               # closest unvisited place
        if d > dist[node]:
            continue                                 # old, longer entry -> ignore
        for neighbour, road in graph[node].items():
            new_d = d + road
            if new_d < dist[neighbour]:              # found a shorter way
                dist[neighbour] = new_d
                previous[neighbour] = node
                heapq.heappush(queue, (new_d, neighbour))
    return dist, previous


def build_path(previous, start, end):
    """Follow the 'previous' links backwards to get the full path."""
    path = []
    node = end
    while node is not None:
        path.append(node)
        node = previous[node]
    path.reverse()
    return path if path[0] == start else []


# =====================================================================
# PHASE 3B: NEAREST-NEIGHBOR TSP APPROXIMATION  (the delivery route)
# =====================================================================
# From the current place, always drive to the nearest stop not yet visited.
# This is fast (not always perfect), which is why it is called an
# "approximation".


def nearest_neighbor_route(graph, depot, stops):
    # Run Dijkstra once from every important place (depot + stops)
    all_dist = {}
    all_prev = {}
    for place in [depot] + list(stops):
        all_dist[place], all_prev[place] = dijkstra(graph, place)

    route = [depot]
    total = 0
    current = depot
    remaining = set(stops)

    while remaining:
        nearest = min(remaining, key=lambda s: all_dist[current][s])
        total += all_dist[current][nearest]
        route.append(nearest)
        remaining.remove(nearest)
        current = nearest

    total += all_dist[current][depot]                # drive back to the depot
    route.append(depot)
    return route, total, all_dist, all_prev


# =====================================================================
# PHASE 4: PERFORMANCE TESTING
# =====================================================================


def make_random_parcels(n, places):
    random.seed(n)                                   # same data every run
    return [{"id": f"P{i+1}", "dest": random.choice(places),
             "weight": random.randint(1, 10), "priority": random.randint(1, 10),
             "deadline": random.randint(1, 10)} for i in range(n)]


def make_random_graph(num_nodes):
    """Make a connected map: a chain of roads plus some extra random roads."""
    random.seed(num_nodes)
    names = [f"N{i}" for i in range(num_nodes)]
    graph = {name: {} for name in names}
    for i in range(num_nodes - 1):                   # chain keeps everything connected
        d = random.randint(1, 10)
        graph[names[i]][names[i + 1]] = d
        graph[names[i + 1]][names[i]] = d
    for _ in range(num_nodes * 2):                   # extra roads
        a, b = random.sample(names, 2)
        d = random.randint(1, 10)
        graph[a][b] = d
        graph[b][a] = d
    return graph, names


def time_it(function, *args):
    start = time.perf_counter()
    function(*args)
    return (time.perf_counter() - start) * 1000      # milliseconds


def run_performance_tests(sizes):
    results = {"sizes": sizes, "merge": [], "bubble": [], "knapsack": [],
               "dijkstra": [], "tsp": []}
    for n in sizes:
        graph, names = make_random_graph(n)
        parcels = make_random_parcels(n, names[1:])
        stops = sorted({p["dest"] for p in parcels})

        results["merge"].append(time_it(merge_sort, parcels))
        results["bubble"].append(time_it(bubble_sort, parcels))
        results["knapsack"].append(time_it(knapsack, parcels, VAN_CAPACITY))
        results["dijkstra"].append(time_it(dijkstra, graph, names[0]))
        results["tsp"].append(time_it(nearest_neighbor_route, graph, names[0], stops))
    return results


def draw_runtime_chart(results, filename):
    import matplotlib
    matplotlib.use("Agg")                            # lets us save without a window
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    sizes = results["sizes"]

    axes[0].plot(sizes, results["merge"], "o-", label="Merge Sort")
    axes[0].plot(sizes, results["bubble"], "o-", label="Bubble Sort")
    axes[0].set_title("Sorting: Merge Sort vs Bubble Sort")

    axes[1].plot(sizes, results["knapsack"], "o-", label="Knapsack (DP)")
    axes[1].plot(sizes, results["dijkstra"], "o-", label="Dijkstra")
    axes[1].plot(sizes, results["tsp"], "o-", label="Nearest Neighbor TSP")
    axes[1].set_title("Main steps of the planner")

    for ax in axes:
        ax.set_xlabel("Number of parcels / places (n)")
        ax.set_ylabel("Time (milliseconds)")
        ax.legend()
        ax.grid(True)
    plt.tight_layout()
    plt.savefig(filename, dpi=120)


# =====================================================================
# MAIN PROGRAM
# =====================================================================


def line(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main():
    parcels = load_parcels("data/parcels.csv")
    graph = load_graph("data/graph.csv")

    line("PHASE 1: INPUT DATA")
    print(f"Depot: {DEPOT} | Van capacity: {VAN_CAPACITY} kg")
    print(f"{'ID':<5}{'Dest':<6}{'Weight':<8}{'Priority':<10}{'Deadline'}")
    for p in parcels:
        print(f"{p['id']:<5}{p['dest']:<6}{p['weight']:<8}{p['priority']:<10}{p['deadline']}")

    # ---------------- Phase 2: sorting + knapsack ----------------
    line("PHASE 2A: PARCELS SORTED BY DEADLINE (then priority)")
    sorted_parcels = merge_sort(parcels)
    for p in sorted_parcels:
        print(f"{p['id']:<5} deadline={p['deadline']}  priority={p['priority']}  weight={p['weight']}kg")

    line("PHASE 2B: KNAPSACK - BEST PARCELS FOR ONE TRIP")
    best_value, chosen, table = knapsack(sorted_parcels, VAN_CAPACITY)
    print("Selected parcels:", [p["id"] for p in chosen])
    print("Total weight    :", sum(p["weight"] for p in chosen), "kg (limit", VAN_CAPACITY, "kg)")
    print("Total priority  :", best_value)
    skipped = [p["id"] for p in sorted_parcels if p not in chosen]
    print("Left for next trip:", skipped)

    print("\nDP table - last row (best value for each capacity 0..25 kg):")
    print(table[len(sorted_parcels)])

    # ---------------- Phase 3: graph + route ----------------
    line("PHASE 3A: DIJKSTRA - SHORTEST PATHS FROM DEPOT " + DEPOT)
    dist, prev = dijkstra(graph, DEPOT)
    for place in sorted(dist):
        path = " -> ".join(build_path(prev, DEPOT, place))
        print(f"{DEPOT} to {place}: {dist[place]:>3} km   path: {path}")

    line("PHASE 3B: DELIVERY ROUTE (Nearest Neighbor)")
    stops = sorted({p["dest"] for p in chosen})
    print("Stops to visit:", stops)
    route, total, all_dist, all_prev = nearest_neighbor_route(graph, DEPOT, stops)
    print("Route order   :", " -> ".join(route))
    print("Leg by leg:")
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]
        full_path = " -> ".join(build_path(all_prev[a], a, b))
        print(f"  {a} to {b}: {all_dist[a][b]} km   (roads: {full_path})")
    print("TOTAL ROUTE LENGTH:", total, "km")

    # ---------------- Phase 4: performance ----------------
    line("PHASE 4: RUNTIME TESTS (milliseconds)")
    sizes = [10, 50, 100, 200, 400]
    results = run_performance_tests(sizes)
    print(f"{'n':<6}{'Merge':<10}{'Bubble':<10}{'Knapsack':<11}{'Dijkstra':<10}{'TSP'}")
    for i, n in enumerate(sizes):
        print(f"{n:<6}{results['merge'][i]:<10.3f}{results['bubble'][i]:<10.3f}"
              f"{results['knapsack'][i]:<11.3f}{results['dijkstra'][i]:<10.3f}"
              f"{results['tsp'][i]:.3f}")
    draw_runtime_chart(results, "outputs/runtime_chart.png")
    print("\nChart saved to outputs/runtime_chart.png")

    # ---------------- Correctness checks ----------------
    line("CORRECTNESS CHECKS")
    assert merge_sort(parcels) == bubble_sort(parcels), "sorts disagree!"
    print("Merge sort and bubble sort give the same order: OK")
    assert sum(p["weight"] for p in chosen) <= VAN_CAPACITY
    print("Chosen parcels fit in the van: OK")
    assert dist["H"] == 17
    print("Dijkstra A->H distance matches hand calculation (17 km): OK")


if __name__ == "__main__":
    main()
