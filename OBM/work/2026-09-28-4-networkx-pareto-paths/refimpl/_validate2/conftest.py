import networkx as nx
from pareto_paths import pareto_paths, pareto_frontier, ParetoIndex
nx.pareto_paths = pareto_paths
nx.pareto_frontier = pareto_frontier
nx.ParetoIndex = ParetoIndex
