from mesa import Model
from mesa.time import BaseScheduler, RandomActivation
from mesa.datacollection import DataCollector
import networkx as nx
import random
import math

from .agents import HumanAgent, HubAgent
from .logger import get_logger
import logging

class BaseCirclesModel(Model):
    def __init__(self, log_level='INFO'):
        super().__init__()
        self.current_time = 0
        self.G = nx.DiGraph()
        
        self.log_level = log_level
        self.logger = None
        self.update_logger()

        # Create and add the HubAgent
        self.hub_agent = HubAgent(self)

        self.datacollector = DataCollector(
            model_reporters={
                "TotalTrusts": lambda m: m.G.number_of_edges(),
                "Network": self.get_graph_data,
                "TotalAgents": lambda m: len(m.schedule.agents) - 1,  # Subtract 1 to exclude HubAgent
                "TotalSupply": lambda m: m.hub_agent.get_total_supply(),
                "AvgBalance": lambda m: m.hub_agent.get_avg_balance(),
                "Gini": lambda m: float(m.hub_agent.calculate_gini()),
                "TotalTransactions": lambda m: int(m.hub_agent.get_total_transactions()),
                "TotalTransactionVolume": lambda m: float(m.hub_agent.get_total_transaction_volume()),
                "TotalMints": lambda m: int(m.hub_agent.get_total_mints()),
                "TotalMintVolume": lambda m: float(m.hub_agent.get_total_mint_volume())
            },
            agent_reporters={
                "Balance": lambda a: a.model.hub_agent.get_balance(a.unique_id) if isinstance(a, HumanAgent) else None,
                "Trusts": lambda a: a.model.hub_agent.get_trusts(a.unique_id) if isinstance(a, HumanAgent) else None,
                "Supply": lambda a: a.model.hub_agent.get_supply(a.unique_id) if isinstance(a, HumanAgent) else None,
                "Mints": lambda a: a.model.hub_agent.get_mints(a.unique_id) if isinstance(a, HumanAgent) else None,
                "Traits": lambda a: a.model.hub_agent.get_traits(a.unique_id) if isinstance(a, HumanAgent) else None,
                "Age": lambda a: int(a.model.current_time - a.created_at) if isinstance(a, HumanAgent) else None,
                "Transactions": lambda a: a.model.hub_agent.get_transactions(a.unique_id) if isinstance(a, HumanAgent) else None
            }
        )

    def update_logger(self):
        self.logger = get_logger(self.__class__.__name__, getattr(logging, self.log_level))

    def step(self):
        self.current_time += 1
        self.logger.info(f"Step start: {self.current_time}")
        try:
            self.schedule.step()
            self.datacollector.collect(self)
        except Exception as e:
            self.logger.error(f"Error during model step: {str(e)}")
        self.logger.info(f"Step end: {self.current_time}")

    def get_graph_data(self):
        return {
            'nodes': [{'id': n} for n in self.G.nodes()],
            'links': [{'source': u, 'target': v} for u, v in self.G.edges()]
        }

class ControlledActivationScheduler(BaseScheduler):
    def __init__(self, model):
        super().__init__(model)
        self.steps = 0

    def step(self):
        self.steps += 1
        agent_count = len(self.agents)
        activation_count = math.ceil(agent_count * self.model.activation_fraction)

        # Always activate the HubAgent
        hub_agent = next(agent for agent in self.agents if isinstance(agent, HubAgent))
        hub_agent.step()
        
        # Randomly activate HumanAgents
        human_agents = [agent for agent in self.agents if isinstance(agent, HumanAgent)]
        activated_agents = random.sample(human_agents, min(activation_count, len(human_agents)))
        for agent in activated_agents:
            agent.step()

        self.model.activated_agents_count = activation_count

class CirclesNetwork(BaseCirclesModel):
    def __init__(self, initial_agents=5, activation_fraction=1, decay_half_life=3, log_level='INFO'):
        super().__init__(log_level)
        self.schedule = ControlledActivationScheduler(self)
        self.add_rate = 0.2
        self.invite_rate = 0.2
        self.establish_trust_rate = 0.1
        self.decay_half_life = decay_half_life
        self.activated_agents_count = 0
        self.activation_fraction = activation_fraction

        self.schedule.add(self.hub_agent)

        # Create initial human agents
        for _ in range(initial_agents):
            self.hub_agent.register_new_human()

    def step(self):
        super().step()
        self.logger.info(f"Agents: {self.schedule.get_agent_count()}, Nodes: {self.G.number_of_nodes()}, Edges: {self.G.number_of_edges()}")

    def update_graph(self):
        self.G.clear_edges()
        for agent in self.schedule.agents:
            if isinstance(agent, HumanAgent):
                self.G.add_node(str(agent.unique_id))
                for trusted_id in agent.trusts:
                    self.G.add_edge(str(agent.unique_id), str(trusted_id))

class CirclesStaticNetwork(BaseCirclesModel):
    def __init__(self, num_agents=100, avg_node_degree=3, mint_probability=0.1, transfer_probability=0.05, log_level='INFO',graph_config=None):
        super().__init__(log_level)
        self.num_agents = num_agents
        self.avg_node_degree = avg_node_degree
        self.mint_probability = mint_probability
        self.transfer_probability = transfer_probability
        self.schedule = RandomActivation(self)

        if graph_config:
            self.initialize_from_config(graph_config)
        else:
            self.initialize_random_graph()


    def initialize_random_graph(self):
        self.G = nx.erdos_renyi_graph(n=self.num_agents, p=self.avg_node_degree/(self.num_agents-1), directed=True)
        for i in range(self.num_agents):
            self.hub_agent.register_new_human()
        for edge in self.G.edges():
            self.hub_agent.establish_trusts(edge[0], edge[1], value=random.randint(50, 150))

    def initialize_from_config(self, graph_config):
        self.G = nx.DiGraph()
        for node, data in graph_config['nodes'].items():
            self.G.add_node(node)
            new_agent = self.hub_agent.register_new_human()
            # Set agent traits if specified
            if 'traits' in data:
                self.hub_agent.humans.traits[new_agent] = data['traits']

        for edge in graph_config['edges']:
            self.G.add_edge(edge['source'], edge['target'])
            self.hub_agent.establish_trusts(edge['source'], edge['target'], value=edge.get('trust', 100))


    def step(self):
        super().step()
        self.perform_mints()
        self.perform_transfers()

    def perform_mints(self):
        for agent in self.schedule.agents:
            if isinstance(agent, HumanAgent) and random.random() < self.mint_probability:
                try:
                    self.hub_agent.mint(agent.unique_id)
                except Exception as e:
                    self.logger.error(f"Error minting for agent {agent.unique_id}: {str(e)}")

    def perform_transfers(self):
        for agent in self.schedule.agents:
            if isinstance(agent, HumanAgent) and random.random() < self.transfer_probability:
                try:
                    neighbors = list(self.G.neighbors(agent.unique_id))
                    if neighbors:
                        receiver = random.choice(neighbors)
                        amount = random.randint(1, 10) * (10 ** 18)  # Random amount between 1 and 10 tokens
                        self.hub_agent.transfer(agent.unique_id, receiver, amount)
                except Exception as e:
                    self.logger.error(f"Error in transfer for agent {agent.unique_id}: {str(e)}")