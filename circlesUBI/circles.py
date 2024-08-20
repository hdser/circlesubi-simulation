from circlesUBI.utils.math import from_int, mul_fixed, add_fixed, sub_fixed, EXA
from circlesUBI.demurrage import Demurrage
import logging

class Circles:

    def __init__(self):
        
        self.MAX_CLAIM_DURATION = 14 * 24
        self.DAYS = 24
        self.HOURS = 1

        self.demurrage = Demurrage()

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    

    def calculate_issuance(self, mint_times, current_time):
        try:
            last_mint_time = max(mint_times)
            start_mint = max(current_time - self.MAX_CLAIM_DURATION, last_mint_time)

            dA = self.demurrage.day_since_day0(start_mint)
            dB = self.demurrage.day_since_day0(current_time)
            n = dB - dA
            inflation_day_zero = 0

            complete_hours = from_int((start_mint - (dA * self.DAYS + inflation_day_zero)) / self.HOURS)
            incomplete_hours = from_int(((dB + 1) * self.DAYS + inflation_day_zero - current_time) / self.HOURS + 0)

            overcount = add_fixed(mul_fixed(self.demurrage.R(n), complete_hours), incomplete_hours)
            issuance = mul_fixed(sub_fixed(self.demurrage.T(n), overcount), EXA)
            
            claimable_period_start = inflation_day_zero + dA * self.DAYS + mul_fixed(complete_hours, self.HOURS)
            claimable_period_end = inflation_day_zero + dB * self.DAYS + self.DAYS - mul_fixed(incomplete_hours, self.HOURS)

            if issuance < 0:
                print("T(1):", T(1), "Issuance:", issuance, "Overcount:", overcount, "Days difference:", n,
                    "Start Mint Time:", start_mint, "dA:", dA, "Current Time:", current_time,
                    "Complete Hours:", complete_hours, "Incomplete Hours:", incomplete_hours)

            return issuance, claimable_period_start, claimable_period_end
        except Exception as e:
            self.logger.error(f"Error calculating issuance: {str(e)}")
            raise

    def mint_and_update_total_supply(self, balance, issuance, current_day, last_updated_day):
        day_diff = current_day - last_updated_day
        new_total_supply = self.demurrage.calculate_discounted_balance(balance, day_diff) + issuance

        if new_total_supply <= self.demurrage.MAX_VALUE:
            balance = new_total_supply
            last_updated_day = current_day
        
        return last_updated_day, balance

    def claim_issuance(self, mint_times, supply, current_time):
        issuance, claimable_period_start, claimable_period_end = self.calculate_issuance(mint_times, current_time)
        if issuance == 0:
            return None

        current_day = current_time // self.DAYS
        last_updated_day = max(supply.keys())
        total_supply = supply[last_updated_day]
        new_last_updated_day, new_total_supply = self.mint_and_update_total_supply(total_supply, issuance, current_day, last_updated_day)

        return new_last_updated_day, new_total_supply, issuance
    
