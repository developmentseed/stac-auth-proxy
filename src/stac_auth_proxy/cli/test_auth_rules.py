#!/usr/bin/env python3
"""
CLI tool for testing STAC auth filter rules.

This tool allows you to test your custom filter classes (ITEMS_FILTER_CLS or
COLLECTIONS_FILTER_CLS) by running them against test cases and validating the
results match your expectations.
"""

import argparse
import asyncio
import importlib
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import yaml
from cql2 import Expr


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_colored(text: str, color: str) -> None:
    """Print colored text to stdout."""
    print(f"{color}{text}{Colors.RESET}")


def load_filter_class(cls_path: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
    """
    Dynamically load and instantiate a filter class.

    Args:
        cls_path: Module path and class name separated by colon (e.g., "module.path:ClassName")
        args: Positional arguments for the class constructor
        kwargs: Keyword arguments for the class constructor

    Returns:
        Instantiated filter class

    Raises:
        ValueError: If cls_path format is invalid
        ImportError: If module cannot be imported
        AttributeError: If class is not found in module

    """
    if ":" not in cls_path:
        raise ValueError(
            f"Invalid class path format: {cls_path}. "
            "Expected format: 'module.path:ClassName'"
        )

    module_path, class_name = cls_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    filter_cls = getattr(module, class_name)
    return filter_cls(*args, **kwargs)


def load_test_file(file_path: Path) -> dict[str, Any]:
    """
    Load test cases from a YAML or JSON file.

    Args:
        file_path: Path to the test file (YAML or JSON)

    Returns:
        Parsed file content

    Raises:
        FileNotFoundError: If test file doesn't exist
        yaml.YAMLError: If YAML file contains invalid syntax
        json.JSONDecodeError: If JSON file contains invalid syntax

    """
    if not file_path.exists():
        raise FileNotFoundError(f"Test file not found: {file_path}")

    with open(file_path) as f:
        # Detect format by file extension
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        else:
            return json.load(f)


async def run_test_case(
    test_case: dict[str, Any],
    filter_instance: Any,
    case_number: int,
) -> tuple[bool, str]:
    """
    Run a single test case.

    Args:
        test_case: Test case configuration containing:
            - name: Test case name (optional)
            - context: Context dict to pass to the filter
            - tests: List of [item, expected] tuples

        filter_instance: Instantiated filter class
        case_number: Test case number for display

    Returns:
        Tuple of (success: bool, message: str)

    """
    context = test_case["context"]
    test_pairs = test_case["tests"]

    try:
        # Generate CQL2 filter from context
        cql2_filter_expr = await filter_instance(context)

        # Parse into Expr
        if isinstance(cql2_filter_expr, str):
            cql2_expr = Expr(cql2_filter_expr)
        else:
            cql2_expr = Expr(**cql2_filter_expr)

        # Validate the expression
        cql2_expr.validate()

    except Exception as e:
        return False, f"Failed to generate or validate CQL2 filter: {e}"

    # Test each item
    failures = []
    for idx, (item, expected_result) in enumerate(test_pairs):
        try:
            actual_result = cql2_expr.matches(item)
            if actual_result != expected_result:
                item_id = item.get("id", f"item #{idx}")
                failures.append(
                    f"  Item {item_id}: expected {expected_result}, got {actual_result}"
                )
        except Exception as e:
            item_id = item.get("id", f"item #{idx}")
            failures.append(f"  Item {item_id}: error evaluating match - {e}")

    if failures:
        failure_msg = "\n".join(failures)
        return False, f"Item match failures:\n{failure_msg}"

    return True, f"All {len(test_pairs)} items matched expected results"


async def run_tests(
    filter_instance: Any,
    test_data: dict[str, Any],
) -> tuple[int, int]:
    """
    Run all test cases.

    Args:
        filter_instance: Instantiated filter class
        test_data: Test data containing list of test cases

    Returns:
        Tuple of (passed_count, failed_count)

    """
    test_cases = test_data.get("test_cases", [])

    if not test_cases:
        print_colored("Warning: No test cases found in test file", Colors.YELLOW)
        return 0, 0

    print_colored(
        f"\n{Colors.BOLD}Running {len(test_cases)} test case(s)...\n", Colors.BLUE
    )

    passed = 0
    failed = 0

    for idx, test_case in enumerate(test_cases, start=1):
        name = test_case.get("name", f"Test case #{idx}")
        print(f"{Colors.BOLD}[{idx}/{len(test_cases)}]{Colors.RESET} {name}...")

        success, message = await run_test_case(test_case, filter_instance, idx)

        if success:
            print_colored(f"  ✓ PASS: {message}", Colors.GREEN)
            passed += 1
        else:
            print_colored(f"  ✗ FAIL: {message}", Colors.RED)
            failed += 1

        print()  # Empty line between test cases

    return passed, failed


def main() -> int:
    """
    Run the CLI.

    Returns:
        Exit code (0 for success, 1 for failures)

    """
    parser = argparse.ArgumentParser(
        description="Test STAC auth filter rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Example usage:
            # Test a Template filter
            stac-auth-tests \\
                --filter-class "stac_auth_proxy.filters:Template" \\
                --filter-args '["(properties.private = false)"]' \\
                --test-file tests/auth_rules.yaml

            # Test an OPA filter with kwargs
            stac-auth-tests \\
                --filter-class "stac_auth_proxy.filters:Opa" \\
                --filter-args '["http://opa:8181", "stac/items"]' \\
                --filter-kwargs '{"cache_ttl": 30.0}' \\
                --test-file tests/auth_rules.yaml

            # Test a custom filter
            stac-auth-tests \\
                --filter-class "my_module.filters:CustomFilter" \\
                --filter-args '["arg1", "arg2"]' \\
                --test-file tests/my_auth_tests.yaml
            """
        ),
    )

    parser.add_argument(
        "--filter-class",
        required=True,
        help='Filter class path in format "module.path:ClassName"',
    )
    parser.add_argument(
        "--filter-args",
        default="[]",
        help="JSON array of positional arguments for filter class (default: [])",
    )
    parser.add_argument(
        "--filter-kwargs",
        default="{}",
        help="JSON object of keyword arguments for filter class (default: {})",
    )
    parser.add_argument(
        "--test-file",
        type=Path,
        required=True,
        help="Path to YAML or JSON file containing test cases",
    )

    args = parser.parse_args()

    # Parse JSON args
    try:
        filter_args = json.loads(args.filter_args)
        if not isinstance(filter_args, list):
            print_colored("Error: --filter-args must be a JSON array", Colors.RED)
            return 1
    except json.JSONDecodeError as e:
        print_colored(f"Error parsing --filter-args: {e}", Colors.RED)
        return 1

    try:
        filter_kwargs = json.loads(args.filter_kwargs)
        if not isinstance(filter_kwargs, dict):
            print_colored("Error: --filter-kwargs must be a JSON object", Colors.RED)
            return 1
    except json.JSONDecodeError as e:
        print_colored(f"Error parsing --filter-kwargs: {e}", Colors.RED)
        return 1

    # Load filter class
    try:
        print_colored(f"\n{Colors.BOLD}Loading filter class...", Colors.BLUE)
        print(f"  Class: {args.filter_class}")
        print(f"  Args: {filter_args}")
        print(f"  Kwargs: {filter_kwargs}")
        filter_instance = load_filter_class(
            args.filter_class, filter_args, filter_kwargs
        )
        print_colored("  ✓ Filter loaded successfully\n", Colors.GREEN)
    except Exception as e:
        print_colored(f"Error loading filter class: {e}", Colors.RED)
        return 1

    # Load test file
    try:
        print_colored(f"{Colors.BOLD}Loading test file...", Colors.BLUE)
        print(f"  File: {args.test_file}")
        test_data = load_test_file(args.test_file)
        print_colored("  ✓ Test file loaded successfully", Colors.GREEN)
    except Exception as e:
        print_colored(f"Error loading test file: {e}", Colors.RED)
        return 1

    # Run tests
    passed, failed = asyncio.run(run_tests(filter_instance, test_data))

    # Print summary
    print_colored(f"\n{Colors.BOLD}{'=' * 60}", Colors.BLUE)
    print_colored(f"{Colors.BOLD}Test Summary", Colors.BLUE)
    print_colored(f"{Colors.BOLD}{'=' * 60}", Colors.BLUE)
    print_colored(f"Passed: {passed}", Colors.GREEN)
    if failed > 0:
        print_colored(f"Failed: {failed}", Colors.RED)
    else:
        print(f"Failed: {failed}")
    total = passed + failed
    print(f"Total:  {total}")
    print_colored(f"{'=' * 60}\n", Colors.BLUE)

    if failed > 0:
        print_colored("Some tests failed!", Colors.RED)
        return 1
    elif total == 0:
        print_colored("No tests were run!", Colors.YELLOW)
        return 1
    else:
        print_colored("All tests passed!", Colors.GREEN)
        return 0


if __name__ == "__main__":
    sys.exit(main())
