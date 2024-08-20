from mesa import Model
from mesa.time import BaseScheduler
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from datetime import datetime
import networkx as nx
import random
import math
from circlesUBI import Hub, HumanEnvironment

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

        #activated_agents = random.sample(self.agents, activation_count)
        #for agent in activated_agents:
        #    agent.step()
        
        self.model.activated_agents_count = activation_count

class CirclesNetwork(Model):
    def __init__(self, initial_agents=5, activation_fraction=1, decay_half_life=3, log_level='INFO'):
        super().__init__()
        #self.schedule = RandomActivation(self)
        self.schedule = ControlledActivationScheduler(self)
        self.humans = HumanEnvironment()
        self.hub = Hub(self.humans)
        self.add_rate = 0.2
        self.invite_rate = 0.2
        self.establish_trust_rate = 0.1
        self.decay_half_life = decay_half_life
        #self.current_time = int(datetime(2020, 1, 1).timestamp())
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
        #for _ in range(initial_agents):
        #    self.add_initial_agent()

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
            self.hub.register_human(self.current_time, new_human_id)
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


class CirclesNetworkGrid(CirclesNetwork):
    """ A model with some number of agents. """
    def __init__(self, add_rate=0.02, invite_rate=0.02, initial_agents=1):
        super().__init__()
        self.G = nx.DiGraph()
        self.G.add_nodes_from(range(0, 1000))
        self.grid = NetworkGrid(self.G)


""" 
# Example of running the model
model = CirclesNetwork(initial_agents=0)  
#print(model.hub.avatars)
for i in range(150):  # Run the model for 10 steps
    model.step()
    print(f"Step {i} completed")

df = model.datacollector.get_model_vars_dataframe()

G = df.iloc[149]['Network']
print(G)
plot_adjacency_matrix(G)
#for agent in model.schedule.agents:
#    print(f"Agent ID: {agent.unique_id}, Balance: {agent.balance}, Trusts: {agent.trusts}")
print(model.datacollector.get_model_vars_dataframe())
#print(model.datacollector.get_agent_vars_dataframe())

#agent_data = model.datacollector.get_agent_vars_dataframe()
#last_state_per_agent = agent_data.groupby(level="AgentID").last()

#print(last_state_per_agent['Trusts'].apply(lambda x: list(x.keys()) if isinstance(x, dict) else []))

"""