from mesa import Model
from mesa.time import BaseScheduler
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from datetime import datetime
import networkx as nx
import random
import math

from .agents import HumanAgent, HubAgent
from .logger import get_logger
import logging


def count_trust_relationships(model):
    """Count the number of trust relationships in the model."""
    return sum(len(agent.trusts) for agent in model.schedule.agents)


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

class CirclesNetwork(Model):
    def __init__(self, initial_agents=5, activation_fraction=1, decay_half_life=3, log_level='INFO'):
        super().__init__()
        #self.schedule = RandomActivation(self)
        self.schedule = ControlledActivationScheduler(self)
        self.add_rate = 0.2
        self.invite_rate = 0.2
        self.establish_trust_rate = 0.1
        self.decay_half_life = decay_half_life
        self.current_time = 0
        self.G = nx.DiGraph()
        
        self.activated_agents_count = 0
        self.activation_fraction = activation_fraction
        
        self.log_level = log_level
        self.logger = None
        self.update_logger()

        # Create and add the HubAgent
        self.hub_agent = HubAgent(self)
        self.schedule.add(self.hub_agent)

        # Create initial human agents
        for _ in range(initial_agents):
            self.hub_agent.register_new_human()

        self.datacollector = DataCollector(
            model_reporters={
                "TotalTrusts": self.count_trust_relationships,
                "Network": self.get_graph_data,
                "ActivatedAgents": lambda m: m.activated_agents_count,
                "TotalAgents": lambda m: len(m.schedule.agents) - 1  # Subtract 1 to exclude HubAgent
            },
            agent_reporters={
                "Balance": lambda a: a.balance if isinstance(a, HumanAgent) else None,
                "Trusts": lambda a: a.trusts if isinstance(a, HumanAgent) else None,
                "Supply": lambda a: a.supply if isinstance(a, HumanAgent) else None,
                "Balances": lambda a: a.balances if isinstance(a, HumanAgent) else None,
                "Mints": lambda a: a.mints if isinstance(a, HumanAgent) else None,
                "Traits": lambda a: a.traits if isinstance(a, HumanAgent) else None,
                "Age": lambda a: (self.current_time - a.created_at) if isinstance(a, HumanAgent) else None
            } 
        )

    def update_logger(self):
        self.logger = get_logger("CirclesNetwork", getattr(logging, self.log_level))

    def add_initial_agent(self):
        try:
            new_human_id = self.next_id()
            self.hub_agent.register_human(self.current_time, new_human_id)
            new_agent = HumanAgent(new_human_id, self, init_balance=50)
            self.schedule.add(new_agent)
            self.G.add_node(new_human_id)
            self.logger.info(f"Added initial agent with ID: {new_human_id}")
        except Exception as e:
            self.logger.error(f"Error adding initial agent: {str(e)}")

    def step(self):
        self.current_time += 1 #86400
        self.logger.info(f"Step start: {self.current_time},  Agents: {self.schedule.get_agent_count()}, Nodes: {self.G.number_of_nodes()}, Edges: {self.G.number_of_edges()}")
        try:
            self.activated_agents_count = 0
            self.schedule.step()
            self.datacollector.collect(self)
        except Exception as e:
            self.logger.error(f"Error during model step: {str(e)}")
        self.logger.info(f"Step end: {self.current_time}, Agents: {self.schedule.get_agent_count() -1}, Nodes: {self.G.number_of_nodes()}, Edges: {self.G.number_of_edges()}")

    def update_graph(self):
        # Clear existing edges
        self.G.clear_edges()
        
        # Add nodes and edges based on current trust relationships
        for agent in self.schedule.agents:
            if isinstance(agent, HumanAgent):
                self.G.add_node(str(agent.unique_id))
                for trusted_id in agent.trusts:
                    self.G.add_edge(str(agent.unique_id), str(trusted_id))
    
    def get_graph_data(self):
        return {
            'nodes': [{'id': n} for n in self.G.nodes()],
            'links': [{'source': u, 'target': v} for u, v in self.G.edges()]
        }

    def count_trust_relationships(self):
        return sum(len(agent.trusts) for agent in self.schedule.agents if isinstance(agent, HumanAgent))

    def next_id(self):
        return self.schedule.get_agent_count()


class CirclesStaticNetwork(Model):
    def __init__(self, num_agents=100, avg_node_degree=3, mint_probability=0.1, transfer_probability=0.05, log_level='INFO'):
        super().__init__()
        self.num_agents = num_agents
        self.avg_node_degree = avg_node_degree
        self.mint_probability = mint_probability
        self.transfer_probability = transfer_probability
        self.schedule = RandomActivation(self)
        self.current_time = 0
        self.G = nx.erdos_renyi_graph(n=num_agents, p=avg_node_degree/(num_agents-1), directed=True)
        
        self.log_level = log_level
        self.logger = get_logger("CirclesStaticNetwork", getattr(logging, self.log_level))


        # Create HubAgent
        self.hub_agent = HubAgent(self)
        #self.schedule.add(self.hub_agent)

        # Create and add HumanAgents
        for i in range(num_agents):
            self.hub_agent.register_new_human()

        # Establish trust relationships based on the generated graph
        for edge in self.G.edges():
            self.hub_agent.establish_trusts(edge[0], edge[1], value=random.randint(50, 150))

        self.datacollector = DataCollector(
            model_reporters={
                "TotalTrusts": self.count_trust_relationships,
                "TotalSupply": self.get_total_supply,
                "AvgBalance": self.get_avg_balance,
                "Gini": self.calculate_gini,
                "ActiveAgents": lambda m: m.schedule.get_agent_count() - 1,  # Exclude HubAgent
            },
            agent_reporters={
                "Balance": lambda a: a.balance if isinstance(a, HumanAgent) else None,
                "Supply": lambda a: a.supply if isinstance(a, HumanAgent) else None,
            }
        )

    def step(self):
        self.current_time += 1
        self.logger.info(f"Step start: {self.current_time}")
        
        try:
            self.schedule.step()
            self.perform_mints()
            self.perform_transfers()
            self.datacollector.collect(self)
        except Exception as e:
            self.logger.error(f"Error during model step: {str(e)}")
        
        self.logger.info(f"Step end: {self.current_time}")

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

    def count_trust_relationships(self):
        return self.G.number_of_edges()

    def get_total_supply(self):
        return self.hub_agent.get_total_supply()

    def get_avg_balance(self):
        return self.hub_agent.get_avg_balance()

    def calculate_gini(self):
        return self.hub_agent.calculate_gini()

