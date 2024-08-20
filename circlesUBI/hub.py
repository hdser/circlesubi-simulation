import random
import logging
import numpy as np
from circlesUBI.utils.math import mul_fixed, EXA
from circlesUBI.demurrage import Demurrage 
from circlesUBI.circles import Circles
from dataclasses import dataclass, field

from typing import TypedDict, List, Callable, NamedTuple
from datetime import datetime

@dataclass
class HumanEnvironment:
    population_size: int = 0
    traits: dict = field(default_factory=dict)
    balance: dict = field(default_factory=dict)
    supply: dict = field(default_factory=dict)
    trusts: dict = field(default_factory=dict)
    mints: dict = field(default_factory=dict)
    #trusts_log: list = field(default_factory=list)
    groups: dict = field(default_factory=dict)

    def add_human(self, human_id, traits, balance, supply, mints):
        self.traits[human_id] = traits
        self.balance[human_id] = balance
        self.supply[human_id] = supply
        self.mints[human_id] = mints
        self.population_size += 1

    def add_trust(self, human_id, trusting_on_human_id, trust_data):
        if human_id not in self.trusts:
            self.trusts[human_id] = {}
        if trusting_on_human_id in self.trusts[human_id]:
            return
        self.trusts[human_id][trusting_on_human_id] = trust_data
        #self.trusts_log.append((human_id, trusting_on_human_id, trust_data))

    def update_balance(self, current_time, human_id, change):
        if human_id in self.balance:
            # Assuming balance stores a history of balances keyed by dates, get the most recent balance.
            most_recent_date = max(self.balance[human_id][human_id].keys())
            most_recent_balance = self.balance[human_id][human_id][most_recent_date]
            new_balance = most_recent_balance + change
            if new_balance > 0:
                current_date = current_time
                self.balance[human_id][human_id][current_date] = new_balance
            return new_balance
        else:
            raise ValueError("Human ID not found in balances")
        
    def default_traits(self, created_at, invited_by=None):
        """Generates default traits for a new human."""
        return {
            'sociability': random.uniform(-3,3),
            'influence': random.uniform(-3,3),
            'evilness': random.uniform(-3,3),
            'invited_by': invited_by,
            'created_at': created_at
        }

class Hub:
    def __init__(self, environment):
        self.avatars = environment
        self.new_host_balances = {}
        self.demurrage = Demurrage()
        self.circles = Circles()

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)


    def register_human(self, created_at, human_id, invited_by=None, init_native_balance=50):
        try:
            traits = self.avatars.default_traits(created_at, invited_by)
            initial_balance = {human_id: {created_at: mul_fixed(init_native_balance, EXA)}}
            initial_supply = {created_at: mul_fixed(init_native_balance, EXA)}
            mints = {
                created_at: {
                    'day': self.demurrage.day_since_day0(created_at),
                    'issuance': init_native_balance * EXA
                }
            }
            self.avatars.add_human(human_id, traits, initial_balance, initial_supply, mints)
        except Exception as e:
            self.logger.error(f"Error registering human {human_id}: {str(e)}")
            raise

    def establish_trusts(self,current_time, human_id, trusting_on_human_id, value = 100, trust_duration = 1e9):
        try:
            trust_data = {
                'created_at': current_time,
                'amount': mul_fixed(value, EXA),
                'duration': trust_duration
            }
            self.avatars.add_trust(human_id, trusting_on_human_id, trust_data)
        except Exception as e:
            self.logger.error(f"Error establishing trust between {human_id} and {trusting_on_human_id}: {str(e)}")
            raise

    def invite_human(self, current_time, new_human_id, invited_by, init_native_balance=50):
        try:
            new_host_balance = self.avatars.update_balance(current_time, invited_by, -mul_fixed(10, EXA))
            if new_host_balance >= 0:
                self.register_human(current_time, new_human_id, invited_by, init_native_balance)
                self.establish_trusts(current_time, invited_by, new_human_id, value=100, trust_duration=1e9)
                self.logger.info(f"Human {new_human_id} invited by {invited_by}")
            else:
                self.logger.warning(f"Insufficient balance for {invited_by} to invite {new_human_id}")
                raise ValueError("Insufficient balance for invitation")
        except Exception as e:
            self.logger.error(f"Error inviting human {new_human_id}: {str(e)}")
            raise

    def mint(self, human_id, current_time):
        try:
            mint_times = self.avatars.mints[human_id].keys()
            supply = self.avatars.supply[human_id]
            
            issuance, claimable_period_start, claimable_period_end = self.circles.calculate_issuance(mint_times, current_time)
            if issuance == 0:
                self.logger.info(f"No issuance for human {human_id} at time {current_time}")
                return None

            current_day = self.demurrage.day_since_day0(current_time)
            last_updated_day = max(supply.keys())
            total_supply = supply[last_updated_day]
            
            new_last_updated_day, new_total_supply = self.circles.mint_and_update_total_supply(total_supply, issuance, current_day, last_updated_day)
            
            self.avatars.mints[human_id][current_time] = {
                'day': new_last_updated_day,
                'issuance': issuance
            }
            self.avatars.supply[human_id][current_time] = new_total_supply
            
            # Update balance
            self.avatars.update_balance(current_time, human_id, issuance)
            
            self.logger.info(f"Minted {issuance} for human {human_id} at time {current_time}")
            return issuance
        except Exception as e:
            self.logger.error(f"Error minting for human {human_id}: {str(e)}")
            raise

    def burn(self, human_id, amount, current_time):
        try:
            current_balance = self.avatars.balance[human_id][human_id][max(self.avatars.balance[human_id][human_id].keys())]
            if current_balance < amount:
                self.logger.warning(f"Insufficient balance for human {human_id} to burn {amount}")
                raise ValueError("Insufficient balance for burning")
            
            new_balance = self.avatars.update_balance(current_time, human_id, -amount)
            
            # Update supply
            last_supply_time = max(self.avatars.supply[human_id].keys())
            current_supply = self.avatars.supply[human_id][last_supply_time]
            new_supply = current_supply - amount
            self.avatars.supply[human_id][current_time] = new_supply
            
            self.logger.info(f"Burned {amount} for human {human_id} at time {current_time}")
            return new_balance, new_supply
        except Exception as e:
            self.logger.error(f"Error burning for human {human_id}: {str(e)}")
            raise

    def transfer(self, sender_id, receiver_id, amount, current_time):
        try:
            # Check if sender is not same as receiver
            if sender_id == receiver_id:
                self.logger.warning(f"Sender and receiber are same!")
                raise ValueError("Sender and receiber are same")
            
            # Check if sender has sufficient balance
            sender_balance = self.avatars.balance[sender_id][sender_id][max(self.avatars.balance[sender_id][sender_id].keys())]
            if sender_balance < amount:
                self.logger.warning(f"Insufficient balance for human {sender_id} to transfer {amount}")
                raise ValueError("Insufficient balance for transfer")
            
            # Check if receiver trusts sender and if the trust amount is sufficient
            if receiver_id not in self.avatars.trusts or sender_id not in self.avatars.trusts[receiver_id]:
                self.logger.warning(f"Human {receiver_id} does not trust human {sender_id}")
                raise ValueError("Receiver does not trust sender")
            
            trust_data = self.avatars.trusts[receiver_id][sender_id]
            trust_amount = trust_data['amount']
            if trust_amount < amount:
                self.logger.warning(f"Transfer amount {amount} exceeds trust amount {trust_amount}")
                raise ValueError("Transfer amount exceeds trust amount")
            
            # Check if trust has expired
            if 'duration' in trust_data and current_time > trust_data['created_at'] + trust_data['duration']:
                self.logger.warning(f"Trust from {receiver_id} to {sender_id} has expired")
                raise ValueError("Trust has expired")
            
            # Deduct amount from sender
            new_sender_balance = self.avatars.update_balance(current_time, sender_id, -amount)
            
            # Add amount to receiver
            new_receiver_balance = self.avatars.update_balance(current_time, receiver_id, amount)
            
            # Update sender's supply
            self.update_supply(sender_id, current_time)
            
            # Update receiver's supply
            self.update_supply(receiver_id, current_time)
            
            self.logger.info(f"Transferred {amount} from human {sender_id} to human {receiver_id} at time {current_time}")
            return new_sender_balance, new_receiver_balance
        except Exception as e:
            self.logger.error(f"Error transferring {amount} from {sender_id} to {receiver_id}: {str(e)}")
            raise

    def update_supply(self, human_id, current_time):
        last_supply_time = max(self.avatars.supply[human_id].keys())
        last_supply = self.avatars.supply[human_id][last_supply_time]
        days_passed = self.demurrage.day_since_day0(current_time) - self.demurrage.day_since_day0(last_supply_time)
        
        if days_passed > 0:
            new_supply = self.circles.calculate_discounted_balance(last_supply, days_passed)
            self.avatars.supply[human_id][current_time] = new_supply
            return new_supply
        return last_supply