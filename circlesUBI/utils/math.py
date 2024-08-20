from decimal import Decimal, getcontext

# Set the precision high enough to accommodate 64.64 fixed-point calculations
getcontext().prec = 76

MIN_64x64 = Decimal('-9223372036854775808') * (Decimal(2) ** Decimal(64))  # 2^63 shifted for fixed-point
MAX_64x64 = Decimal('9223372036854775807') * (Decimal(2) ** Decimal(64))   # (2^63 - 1) shifted

EXA = 10 ** 18

def from_int(x):
    """Convert an integer to a 64.64 fixed-point number."""
    return Decimal(x) * (Decimal(2) ** Decimal(64))

def int128_to_decimal(value):
    """Converts a 64.64 fixed-point integer (Solidity-style) to a Decimal."""
    return Decimal(value) / (Decimal(2) ** Decimal(64))

def pow_fixed(x, y):
    """Raise a 64.64 fixed-point number (as Decimal) to an integer power."""
    # Convert x back to a float-like decimal for exponentiation
    normalized_x = x / (Decimal(2) ** Decimal(64))
    power_result = normalized_x ** Decimal(y)
    # Scale back to fixed-point representation
    return power_result * (Decimal(2) ** Decimal(64))

def mul_fixed(x, y):
    """Multiply a 64.64 fixed-point number by an integer."""
    result = x * Decimal(y)
    # Return the result in integer form, assuming y was already in integer form
    return int(result / (Decimal(2) ** Decimal(64)))

def add_fixed(x, y):
    """Add two 64.64 fixed-point numbers, checking for overflow."""
    result = x + y
    if result < MIN_64x64 or result > MAX_64x64:
        raise OverflowError("Fixed-point addition overflow/underflow")
    return result

def sub_fixed(x, y):
    """Subtract two 64.64 fixed-point numbers, checking for overflow."""
    result = x - y
    if result < MIN_64x64 or result > MAX_64x64:
        raise OverflowError("Fixed-point subtraction overflow/underflow")
    return result