"""Sample module for testing PyCLIDE features."""


def hello_world(name: str) -> str:
    """
    Returns a greeting message.

    Args:
        name: The name to greet

    Returns:
        A greeting string
    """
    message = f"Hello, {name}!"
    return message


def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    result = a + b
    return result


class Calculator:
    """A simple calculator class."""

    def __init__(self, initial_value: int = 0):
        self.value = initial_value

    def add(self, x: int) -> int:
        """Add a number to the current value."""
        self.value += x
        return self.value

    def multiply(self, x: int) -> int:
        """Multiply the current value by a number."""
        self.value *= x
        return self.value

    def get_value(self) -> int:
        """Get the current value."""
        return self.value


class AdvancedCalculator(Calculator):
    """An advanced calculator with more operations."""

    def power(self, exponent: int) -> int:
        """Raise the current value to a power."""
        self.value = self.value ** exponent
        return self.value


# Some module-level usage
calc = Calculator(10)
calc.add(5)
result = calc.get_value()