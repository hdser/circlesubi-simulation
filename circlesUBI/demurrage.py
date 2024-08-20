from circlesUBI.utils.math import int128_to_decimal, pow_fixed, mul_fixed, from_int
from decimal import Decimal
import logging


class Demurrage:

    def __init__(self):
        
        self.GAMMA_64x64 = Decimal('18443079296116538654')
        self.BETA_64x64 = Decimal('18450409579521241655')
        self.GAMMA = Decimal('0.9998013320085989574306134065681911664857225676913333806934')
        self.MAX_VALUE = (2 ** 192) - 1
        self.DEMURRAGE_WINDOW = 24

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def day_since_day0(self, time):
        inflation_day_zero = 0
        return (time - inflation_day_zero) // self.DEMURRAGE_WINDOW

    def convert_inflationary_to_demurrage_value(self, inflationary_value, days):
        r = pow_fixed(self.GAMMA_64x64, days)
        return mul_fixed(r, inflationary_value)

    def calculate_demurrage_factor(self, day_diff):
        return pow_fixed(self.GAMMA_64x64, day_diff)

    def calculate_inflationary_balance(self, balance, day_updated):
        i = pow_fixed(self.BETA_64x64, day_updated)
        return mul_fixed(i, balance)

    def calculate_discounted_balance(self, balance, day_diff):
        if day_diff == 0:
            return balance
        demu_factor = self.calculate_demurrage_factor(day_diff)
        return mul_fixed(demu_factor, balance)

    def T(self, n):
        gamma_n = self.GAMMA**Decimal(n)
        result = Decimal('24') * (
            (gamma_n - Decimal('1')) / (self.GAMMA - Decimal('1')) + gamma_n
        )
        fixed_result = from_int(result)
        return round(fixed_result)

    def R(self, n):
        result = self.GAMMA**Decimal(n)
        fixed_result = from_int(result)
        return round(fixed_result)