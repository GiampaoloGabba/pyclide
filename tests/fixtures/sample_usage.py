"""Sample file that uses the sample_module."""

from sample_module import hello_world, Calculator, calculate_sum


def main():
    """Main function demonstrating usage."""
    # Test hello_world function
    greeting = hello_world("Alice")
    print(greeting)

    # Test Calculator class
    my_calc = Calculator(100)
    my_calc.add(50)
    my_calc.multiply(2)

    # Test calculate_sum
    total = calculate_sum(10, 20)

    return total


if __name__ == "__main__":
    result = main()
    print(f"Result: {result}")