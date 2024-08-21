from circlesUBI import Hub, HumanEnvironment
from mesa import Agent
from .logger import get_logger
import random
import math

class HubAgent(Agent):
    def __init__(self, model):
        super().__init__("Hub", model)
        self.logger = get_logger("HubAgent")
        self.humans = HumanEnvironment()
        self.hub = Hub(self.humans)
        self.next_human_id = 0

    def step(self):
        self.logger.debug("HubAgent stepping")

    def register_new_human(self):
        try:
            new_human_id = self.get_next_human_id()
            current_time = self.model.current_time
            self.hub.register_human(current_time, new_human_id)
            
            # Create and add HumanAgent
            new_agent = HumanAgent(new_human_id, self.model)
            self.model.schedule.add(new_agent)
            self.model.G.add_node(new_human_id)
            
            self.logger.debug(f"HubAgent registered new human with ID: {new_human_id}")
            return new_human_id
        except Exception as e:
            self.logger.error(f"Error in register_new_human: {str(e)}")

    def get_next_human_id(self):
        self.next_human_id += 1
        return self.next_human_id

    def invite_human(self, inviter_id, init_native_balance=50):
        try:
            current_time = self.model.current_time
            new_human_id = self.get_next_human_id()
            self.hub.invite_human(current_time, new_human_id, inviter_id, init_native_balance)
            
            # Create and add HumanAgent
            new_agent = HumanAgent(new_human_id, self.model)
            self.model.schedule.add(new_agent)
            self.model.G.add_node(new_human_id)
            
            # Update graph for the new trust relationship
            self.model.G.add_edge(inviter_id, new_human_id, weight=100)
            
            self.logger.info(f"HubAgent invited new human {new_human_id}, invited by {inviter_id}")
            return new_human_id
        except Exception as e:
            self.logger.error(f"Error in invite_human by {inviter_id}: {str(e)}")

    def mint(self, human_id):
        try:
            current_time = self.model.current_time
            issuance = self.hub.mint(human_id, current_time)
            self.logger.info(f"HubAgent minted {issuance} for human {human_id}")
            return issuance
        except Exception as e:
            self.logger.error(f"Error in mint for human {human_id}: {str(e)}")

    def transfer(self, sender_id, receiver_id, amount):
        try:
            current_time = self.model.current_time
            new_sender_balance, new_receiver_balance = self.hub.transfer(sender_id, receiver_id, amount, current_time)
            self.logger.info(f"HubAgent transferred {amount} from human {sender_id} to human {receiver_id}")
            return new_sender_balance, new_receiver_balance
        except Exception as e:
            self.logger.error(f"Error in transfer from {sender_id} to {receiver_id}: {str(e)}")

    def establish_trusts(self, human_id, trusting_on_human_id, value=100, trust_duration=1e9):
        try:
            current_time = self.model.current_time
            self.hub.establish_trusts(current_time, human_id, trusting_on_human_id, value, trust_duration)
            self.model.G.add_edge(human_id, trusting_on_human_id, weight=value)
            self.logger.debug(f"HubAgent established trust between {human_id} and {trusting_on_human_id}")
        except Exception as e:
            self.logger.error(f"Error in establish_trusts between {human_id} and {trusting_on_human_id}: {str(e)}")

    def get_total_supply(self):
        return sum(self.humans.supply[agent_id][max(self.humans.supply[agent_id].keys())]
                   for agent_id in self.humans.supply)

    def get_avg_balance(self):
        balances = [self.humans.balance[agent_id][agent_id][max(self.humans.balance[agent_id][agent_id].keys())]
                    for agent_id in self.humans.balance]
        return sum(balances) / len(balances) if balances else 0

    def calculate_gini(self):
        balances = [self.humans.balance[agent_id][agent_id][max(self.humans.balance[agent_id][agent_id].keys())]
                    for agent_id in self.humans.balance]
        if not balances:
            return 0
        balances.sort()
        n = len(balances)
        index = [i / n for i in range(n)]
        return 1 - 2 * sum(index[i] * balances[i] for i in range(n)) / sum(balances)

    def get_balance(self, agent_id):
        return self.humans.balance.get(agent_id, {})

    def get_supply(self, agent_id):
        return self.humans.supply.get(agent_id, {})

    def get_trusts(self, agent_id):
        return self.humans.trusts.get(agent_id, {})

    def get_mints(self, agent_id):
        return self.humans.mints.get(agent_id, {})

    def get_traits(self, agent_id):
        return self.humans.traits.get(agent_id, {})

class HumanAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.created_at = model.current_time
        self.logger = get_logger(f"HumanAgent_{unique_id}")

    def step(self):
        self.logger.debug(f"Agent {self.unique_id} stepping")
        try:
            self.transfer()
            if random.random() < self.calculate_probability("invite"):
                self.invite_new_human()
            if random.random() < self.calculate_probability("establish_trust"):
                self.establish_new_trust()
            if random.random() < self.calculate_probability("mint"):
                self.mint()
        except Exception as e:
            self.logger.error(f"Error in step for Agent {self.unique_id}: {str(e)}")

    def calculate_probability(self, action_type):
        base_rate = getattr(self.model, f"{action_type}_rate", 0.1)
        age = (self.model.current_time - self.created_at) 
        decay_factor = math.exp(-age / self.model.decay_half_life)

        traits = self.model.hub_agent.get_traits(self.unique_id)
        if action_type == "invite":
            prob = self.sigmoid(base_rate + traits['influence'] - traits['evilness'])
        elif action_type == "establish_trust":
            prob = self.sigmoid(base_rate + 0.8*traits['sociability'] - 0.2*traits['evilness'])
        elif action_type == "mint":
            prob = 0.5
        else:
            prob = base_rate

        return base_rate + (prob - base_rate) * decay_factor

    def sigmoid(self, x):
        return 0.5 / (1 + math.exp(-x))

    def invite_new_human(self):
        self.model.hub_agent.invite_human(self.unique_id)

    def establish_new_trust(self):
        other_agents = [agent for agent in self.model.schedule.agents if isinstance(agent, HumanAgent) and agent.unique_id != self.unique_id]
        if other_agents:
            trusted_agent = random.choice(other_agents)
            self.model.hub_agent.establish_trusts(self.unique_id, trusted_agent.unique_id)

    def mint(self):
        self.model.hub_agent.mint(self.unique_id)

    def transfer(self):
        trusts = self.model.hub_agent.get_trusts(self.unique_id)
        for trusted_id in trusts:
            self.model.hub_agent.transfer(self.unique_id, trusted_id, 1)  # Transfer 1 token to each trusted agent