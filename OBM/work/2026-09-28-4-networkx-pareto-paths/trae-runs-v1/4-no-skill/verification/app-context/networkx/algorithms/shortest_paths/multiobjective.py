"""
Multiobjective (Pareto) shortest path algorithms.
"""

from bisect import bisect_left
from heapq import heappop, heappush
from itertools import count

import networkx as nx

__all__ = ["pareto_paths"]


@nx._dispatchable(edge_attrs={"weight": 0, "cost": 0})
def pareto_paths(
    G,
    source,
    target,
    weight="weight",
    cost="cost",
    *,
    max_cost=None,
    max_weight=None,
):
    """Find all non-dominated (Pareto optimal) paths from source to target.

    Each edge carries two additive attributes: ``cost`` and ``weight``
    (the attribute names are configurable). A ``(cost, weight)`` pair
    *dominates* another pair if both components are no larger and at least
    one is strictly smaller. This function returns every reachable
    non-dominated pair together with a simple path realizing exactly that
    pair.

    Parameters
    ----------
    G : NetworkX graph
        A (possibly directed) graph. Every edge may carry the two numeric
        attributes ``cost`` and ``weight``; a missing attribute counts as
        zero. MultiGraph and MultiDiGraph are not supported.

    source : node
        Starting node.

    target : node
        Ending node.

    weight : string (default: "weight")
        Name of the edge attribute holding the first additive metric.

    cost : string (default: "cost")
        Name of the edge attribute holding the second additive metric.

    max_cost : number, optional
        If given, only paths with total cost at most ``max_cost`` are
        considered.

    max_weight : number, optional
        If given, only paths with total weight at most ``max_weight`` are
        considered.

    Returns
    -------
    records : list of dicts
        A list of ``{"cost": c, "weight": w, "path": path}`` records, one
        per reachable non-dominated pair. ``path`` is a simple path (a list
        of nodes starting with `source` and ending with `target`) whose edge
        attributes sum to exactly ``(c, w)``. Records are sorted by cost in
        ascending order, and by weight in ascending order for equal costs
        (so weights strictly decrease as costs increase along the frontier).
        If `source` equals `target`, the single record
        ``{"cost": 0, "weight": 0, "path": [source]}`` is returned. If the
        target is reachable but no path respects the given bounds, an empty
        list is returned.

    Raises
    ------
    NodeNotFound
        If `source` or `target` is not in `G`.

    NetworkXNoPath
        If `target` is in `G` but no path exists from `source` to `target`.

    NetworkXNotImplemented
        If `G` is a MultiGraph or MultiDiGraph.

    ValueError
        If an edge reached during the search has a negative value for one of
        the two attributes.

    Examples
    --------
    >>> G = nx.DiGraph()
    >>> G.add_edge("a", "b", cost=1, weight=4)
    >>> G.add_edge("a", "c", cost=3, weight=2)
    >>> G.add_edge("b", "d", cost=2, weight=2)
    >>> G.add_edge("c", "d", cost=1, weight=2)
    >>> result = nx.pareto_paths(G, "a", "d")
    >>> for record in result:
    ...     print(record["cost"], record["weight"], record["path"])
    3 6 ['a', 'b', 'd']
    4 4 ['a', 'c', 'd']

    Notes
    -----
    The algorithm is a label-setting multiobjective extension of Dijkstra's
    algorithm (Martins' algorithm). Each node keeps the sorted Pareto
    frontier of labels found so far; labels are finalized in lexicographic
    ``(cost, weight)`` order, which is valid because both metrics are
    non-negative. Each label stores a parent pointer; stripping the
    necessarily zero-cost/zero-weight cycles from the parent chain yields a
    simple witness path with identical totals. The function does not modify
    ``G`` and repeated calls return identical results.
    """
    if G.is_multigraph():
        raise nx.NetworkXNotImplemented(
            "pareto_paths not implemented for MultiGraph or MultiDiGraph."
        )
    if source not in G:
        raise nx.NodeNotFound(f"Node {source} not found in graph")
    if target not in G:
        raise nx.NodeNotFound(f"Node {target} not found in graph")

    if source == target:
        return [{"cost": 0, "weight": 0, "path": [source]}]

    # Per-node Pareto frontier kept in three parallel lists, sorted by cost
    # in ascending order. Along a frontier weights are strictly decreasing:
    # a later label with a weight no smaller than an earlier label would be
    # dominated. A label is the list ``[c, w, pred_node, parent, status]``
    # where status is 0 (queued), 1 (settled) or 2 (pruned as dominated).
    frontiers = {}
    src_label = [0, 0, None, None, 0]
    frontiers[source] = ([0], [0], [src_label])

    adj = G._adj
    cost_attr = cost
    weight_attr = weight
    _heappop = heappop
    _heappush = heappush
    _bisect_left = bisect_left
    _next_tie = count(1).__next__
    check_cost_bound = max_cost is not None
    check_weight_bound = max_weight is not None

    # Heap entries carry their label; status marking makes any re-lookup
    # (and bisect) at pop time unnecessary.
    heap = [(0, 0, 0, source, src_label)]

    while heap:
        c, w, _, v, lab = _heappop(heap)
        if lab[4]:
            # Already settled, or pruned from its frontier as dominated.
            continue
        lab[4] = 1

        # Labels at the target never need to be expanded: any walk that
        # reaches the target, leaves it and comes back to it is either
        # dominated by (or equal to) its target prefix.
        if v == target:
            continue

        for u, edgedata in adj[v].items():
            ec = edgedata.get(cost_attr, 0)
            ew = edgedata.get(weight_attr, 0)
            if ec < 0 or ew < 0:
                raise ValueError(
                    "pareto_paths requires non-negative edge attributes, "
                    f"got cost={ec!r}, weight={ew!r} on edge ({v!r}, {u!r})"
                )
            nc = c + ec
            nw = w + ew
            if check_cost_bound and nc > max_cost:
                continue
            if check_weight_bound and nw > max_weight:
                continue

            fentry = frontiers.get(u)
            if fentry is None:
                new_label = [nc, nw, v, lab, 0]
                frontiers[u] = ([nc], [nw], [new_label])
                _heappush(heap, (nc, nw, _next_tie(), u, new_label))
                continue

            costs, weights, labels = fentry
            # A single bisect locates the candidate cost. Frontier weights
            # are strictly decreasing with increasing cost, so the
            # candidate is dominated (or is a duplicate) when the weight of
            # the last label with cost <= nc is no larger than nw.
            k = _bisect_left(costs, nc)
            if k < len(costs) and costs[k] == nc:
                if weights[k] <= nw:
                    continue
            elif k > 0 and weights[k - 1] <= nw:
                continue
            # Prune frontier labels dominated by the candidate: labels with
            # cost >= nc and weight >= nw form a prefix of the tail. They
            # cannot have been settled yet (the candidate precedes them in
            # lexicographic order), so simply mark them pruned.
            stop = k
            n_front = len(weights)
            while stop < n_front and weights[stop] >= nw:
                labels[stop][4] = 2
                stop += 1
            if stop > k:
                del costs[k:stop]
                del weights[k:stop]
                del labels[k:stop]
            new_label = [nc, nw, v, lab, 0]
            costs.insert(k, nc)
            weights.insert(k, nw)
            labels.insert(k, new_label)
            _heappush(heap, (nc, nw, _next_tie(), u, new_label))

    target_entry = frontiers.get(target)
    if target_entry is None or not target_entry[0]:
        # No feasible label at the target: either genuinely unreachable or
        # reachable but every path exceeds a bound.
        if not _unweighted_reachable(adj, source, target):
            raise nx.NetworkXNoPath(f"No path to {target}.")
        return []

    result = []
    for tlab in target_entry[2]:
        path = _witness_path(target, tlab)
        pc, pw = _path_totals(G, path, cost_attr, weight_attr)
        result.append({"cost": pc, "weight": pw, "path": path})
    return result


def _unweighted_reachable(adj, source, target):
    """Return True if target is reachable from source ignoring edge metrics."""
    seen = {source}
    stack = [source]
    while stack:
        v = stack.pop()
        for u in adj[v]:
            if u == target:
                return True
            if u not in seen:
                seen.add(u)
                stack.append(u)
    return False


def _witness_path(target_node, label):
    """Reconstruct a simple witness path for a settled target label.

    Following parent pointers gives a walk from the source to the target.
    For a non-dominated (settled) label every cycle in that walk must have
    zero total cost and zero weight (removing a positive cycle would yield
    a strictly dominating walk), so deleting repeated-node segments
    produces a simple path with exactly the same attribute totals.
    """
    walk = [target_node]
    while label[2] is not None:
        walk.append(label[2])
        label = label[3]
    walk.reverse()

    path = []
    positions = {}
    for node in walk:
        if node in positions:
            p = positions[node]
            for repeated in path[p + 1 :]:
                del positions[repeated]
            del path[p + 1 :]
        else:
            positions[node] = len(path)
            path.append(node)
    return path


def _path_totals(G, path, cost_attr, weight_attr):
    total_cost = 0
    total_weight = 0
    edges = G._adj
    for a, b in zip(path, path[1:]):
        data = edges[a][b]
        total_cost += data.get(cost_attr, 0)
        total_weight += data.get(weight_attr, 0)
    return total_cost, total_weight
