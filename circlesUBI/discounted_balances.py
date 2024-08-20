from circlesUBI.demurrage import Demurrage
from collections import defaultdict

class DiscountedBalanceManager:
    def __init__(self):
        self.discounted_balances = defaultdict(lambda: defaultdict(lambda: {'balance': 0, 'last_updated_day': 0}))
        self.discounted_total_supplies = defaultdict(lambda: {'balance': 0, 'last_updated_day': 0})
        self.inflation_day_zero = 0
        self.demurrage = Demurrage()

    def set_inflation_day_zero(self, timestamp):
        self.inflation_day_zero = timestamp

    def balance_of_on_day(self, account, circle_id, day):
        discounted_balance = self.discounted_balances[circle_id][account]
        if day < discounted_balance['last_updated_day']:
            raise Exception("Day is before last updated day")
        
        day_difference = day - discounted_balance['last_updated_day']
        balance_on_day = self.demurrage.calculate_discounted_balance(discounted_balance['balance'], day_difference)
        discount_cost = discounted_balance['balance'] - balance_on_day
        
        return balance_on_day, discount_cost

    def total_supply(self, time, circle_id):
        total_supply_balance = self.discounted_total_supplies[circle_id]
        today = self.demurrage.day_since_day0(time)
        return self.demurrage.calculate_discounted_balance(
            total_supply_balance['balance'],
            today - total_supply_balance['last_updated_day']
        )

    def inflationary_balance_of(self, account, circle_id):
        discounted_balance = self.discounted_balances[circle_id][account]
        return self.demurrage.calculate_inflationary_balance(
            discounted_balance['balance'],
            discounted_balance['last_updated_day']
        )

    def update_balance(self, account, circle_id, balance, day):
        if balance > self.demurrage.MAX_VALUE:
            raise Exception("Balance exceeds maximum value")
        
        self.discounted_balances[circle_id][account]['balance'] = balance
        self.discounted_balances[circle_id][account]['last_updated_day'] = day

    def discount_and_add_to_balance(self, account, circle_id, value, day):
        discounted_balance = self.discounted_balances[circle_id][account]

        if day < discounted_balance['last_updated_day']:
            raise Exception("Day is before last updated day")
        
        day_difference = day - discounted_balance['last_updated_day']
        discounted_balance_on_day = self.demurrage.calculate_discounted_balance(discounted_balance['balance'], day_difference)
        discount_cost = discounted_balance['balance'] - discounted_balance_on_day
        
        if discount_cost > 0:
            print(f"DiscountCost: {account}, {circle_id}, {discount_cost}")
        
        updated_balance = discounted_balance_on_day + value
        if updated_balance > self.demurrage.MAX_VALUE:
            raise Exception("Balance exceeds maximum value")
        
        discounted_balance['balance'] = updated_balance
        discounted_balance['last_updated_day'] = day