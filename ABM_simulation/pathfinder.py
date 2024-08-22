import networkx as nx
from .logger import get_logger

class PathFinder:
    def __init__(self, graph, hub_agent):
        self.graph = graph
        self.hub_agent = hub_agent
        self.logger = get_logger("PathFinder")

    def find_transfer_paths(self, source, target, max_depth=5):
        """
        Find all valid paths for value transfer from source to target using NetworkX.
        A valid path is one where the trust direction is opposite to the transfer direction.
        """
        # Swap source and target as the transfer direction is opposite to trust direction
        return list(nx.all_simple_paths(self.graph, target, source, cutoff=max_depth))

    def get_max_transfer_amount(self, path, amount):
        """
        Calculate the maximum amount that can be transferred along a given path.
        """
        max_amount = amount
        for i in range(len(path) - 1):
            trustee, truster = path[i], path[i+1]
            trust_amount = self.hub_agent.get_trust_amount(truster, trustee)
            balance = self.hub_agent.get_currency_balance(trustee, trustee)
            max_amount = min(max_amount, trust_amount, balance)
            if max_amount < amount:
                break

        return max_amount

    def find_optimal_transfer_path(self, source, target, amount):
        """
        Find the optimal path for transferring a specific amount from source to target.
        """
        paths = self.find_transfer_paths(source, target)
        optimal_path = None
        max_transferable = 0

        for path in paths:
            path_max = self.get_max_transfer_amount(path, amount)
            if path_max >= amount and (optimal_path is None or len(path) < len(optimal_path)):
                optimal_path = path
                max_transferable = path_max
            elif path_max > max_transferable:
                optimal_path = path
                max_transferable = path_max

        return optimal_path, max_transferable