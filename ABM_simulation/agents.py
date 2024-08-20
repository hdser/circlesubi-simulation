from mesa import Agent
import random
import math
from .logger import get_logger

class HumanAgent(Agent):
    def __init__(self, unique_id, model, init_balance=50):
        super().__init__(unique_id, model)
        self.balance = init_balance
        self.trusts = {}
        self.supply = 0
        self.balances = {}
        self.mints = {}
        self.traits = self.model.hub.avatars.traits[self.unique_id]
        self.created_at = self.traits['created_at']

        self.logger = get_logger(f"HumanAgent_{unique_id}")

    def calculate_probability(self, action_type):
        base_rate = getattr(self.model, f"{action_type}_rate", 0.1)
        age = (self.model.current_time - self.created_at) 

        # Calculate decay factor (1.0 for new agents, approaching 0 for old agents)
        decay_factor = math.exp(-age / self.model.decay_half_life)

        if action_type == "add":
            # Higher sociability increases the chance of adding new humans
            prob = self.sigmoid(base_rate + self.traits['sociability'])
        
        elif action_type == "invite":
            # Higher influence and lower evilness increase the chance of inviting new humans
            prob = self.sigmoid(base_rate + self.traits['influence'] - self.traits['evilness'])
        
        elif action_type == "establish_trust":
            # Higher sociability and lower evilness increase the chance of establishing trust
            prob = self.sigmoid(base_rate + 0.8*self.traits['sociability'] - 0.2*self.traits['evilness'])

        elif action_type == "mint":
            prob = 0.5
        
        else:
            prob = base_rate

        return base_rate + (prob - base_rate) * decay_factor
        
    def sigmoid(self, x):
        return 0.5 / (1 + math.exp(-x))
        
    def step(self):
        self.logger.debug(f"Agent {self.unique_id} stepping")
        self.model.activated_agents_count += 1

        try:
            self.transfer()
           # if random.random() < self.calculate_probability("add"):
           #     self.register_new_humans()
            if random.random() < self.calculate_probability("invite"):
                self.invite_new_human()
            if random.random() < self.calculate_probability("establish_trust"):
                self.establish_new_trust()
            if random.random() < self.calculate_probability("mint"):
                self.mint()
        except Exception as e:
            self.logger.error(f"Error in step for Agent {self.unique_id}: {str(e)}")


    def invite_new_human(self):
        try:
            new_human_id = self.model.next_id()
            current_time = self.model.current_time
            invited_by = self.unique_id

            self.model.hub.invite_human(current_time, new_human_id, invited_by)

            if new_human_id in self.model.humans.traits:
                new_agent = HumanAgent(new_human_id, self.model, init_balance=50)
                self.model.schedule.add(new_agent)
                self.model.G.add_node(new_human_id)
                self.logger.debug(f"Agent {self.unique_id} invited new human with ID: {new_human_id}")
        except Exception as e:
            self.logger.error(f"Error in invite_new_human for Agent {self.unique_id}: {str(e)}")

    def establish_new_trust(self):
        try:
            if len(self.model.schedule.agents) > 1:
                other_agents = [agent for agent in self.model.schedule.agents if agent.unique_id != self.unique_id]
                if other_agents:
                    trusted_agent = random.choice(other_agents)
                    current_time = self.model.current_time
                    trust_value = 100
                    trust_duration = 1e9

                    self.model.hub.establish_trusts(current_time, self.unique_id, trusted_agent.unique_id, trust_value, trust_duration)
                    self.trusts = self.model.hub.avatars.trusts[self.unique_id]
                    
                    self.model.G.add_edge(self.unique_id, trusted_agent.unique_id, weight=trust_value)
                    self.logger.debug(f"Agent {self.unique_id} established trust with agent {trusted_agent.unique_id}")
        except Exception as e:
            self.logger.error(f"Error in establish_new_trust for Agent {self.unique_id}: {str(e)}")


    def mint(self):
        try:
            issuance = self.model.hub.mint(self.unique_id, self.model.current_time)
            self.mints = self.model.hub.avatars.mints[self.unique_id]
            self.logger.info(f"Agent {self.unique_id} minted {issuance} CRC")
        except Exception as e:
            self.logger.error(f"Error on Agent {self.unique_id} mint: {str(e)}")

    def transfer(self):
        try:
            for sender_id in self.model.hub.avatars.trusts.keys():
                new_sender_balance, new_receiver_balance = self.model.hub.transfer(sender_id, self.unique_id,1, self.model.current_time)
            #self.logger.debug(f"Agent {self.unique_id} transfered ")
        except Exception as e:
            self.logger.error(f"Error in transfer for Agent {self.unique_id}: {str(e)}")    

class HubAgent(Agent):
    def __init__(self, model):
        super().__init__("Hub", model)
        self.logger = get_logger("HubAgent")
        self.next_human_id = 0

    def step(self):
        self.logger.debug("HubAgent stepping")
        try:
            if random.random() < self.model.add_rate:
                self.register_new_human()
        except Exception as e:
            self.logger.error(f"Error in HubAgent step: {str(e)}")

    def register_new_human(self):
        try:
            new_human_id = self.get_next_human_id()
            current_time = self.model.current_time
            self.model.hub.register_human(current_time, new_human_id)
            new_agent = HumanAgent(new_human_id, self.model, init_balance=450)
            self.model.schedule.add(new_agent)
            self.model.G.add_node(new_human_id)
            self.logger.debug(f"HubAgent registered new human with ID: {new_human_id}")
        except Exception as e:
            self.logger.error(f"Error in register_new_human: {str(e)}")

    def get_next_human_id(self):
        self.next_human_id += 1
        return self.next_human_id