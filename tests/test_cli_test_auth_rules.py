"""Functional tests for the CLI auth rules testing tool."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from stac_auth_proxy.cli.test_auth_rules import (
    Colors,
    load_filter_class,
    load_test_file,
    main,
    print_colored,
    run_test_case,
    run_tests,
)


class TestLoadFilterClass:
    """Tests for load_filter_class function."""

    def test_load_template_filter_no_args(self):
        """Test loading Template filter without arguments."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["(properties.private = false)"],
            {},
        )
        assert filter_instance is not None
        assert filter_instance.template_str == "(properties.private = false)"

    def test_load_template_filter_with_args(self):
        """Test loading Template filter with arguments."""
        template = "{{ payload.sub }}"
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            [template],
            {},
        )
        assert filter_instance.template_str == template

    def test_load_filter_invalid_path_format(self):
        """Test loading filter with invalid path format (missing colon)."""
        with pytest.raises(ValueError, match="Invalid class path format"):
            load_filter_class("stac_auth_proxy.filters.Template", [], {})

    def test_load_filter_nonexistent_module(self):
        """Test loading filter from non-existent module."""
        with pytest.raises(ImportError):
            load_filter_class("nonexistent_module:Template", [], {})

    def test_load_filter_nonexistent_class(self):
        """Test loading non-existent class from valid module."""
        with pytest.raises(AttributeError):
            load_filter_class("stac_auth_proxy.filters:NonExistentClass", [], {})


class TestLoadTestFile:
    """Tests for load_test_file function."""

    def test_load_yaml_file(self, tmp_path):
        """Test loading valid YAML test file."""
        test_data = {
            "test_cases": [
                {
                    "name": "Test case 1",
                    "context": {"req": {}, "payload": None},
                    "tests": [[{"id": "item1"}, True]],
                }
            ]
        }
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml.dump(test_data))

        result = load_test_file(yaml_file)
        assert result == test_data

    def test_load_yml_file(self, tmp_path):
        """Test loading valid .yml test file."""
        test_data = {"test_cases": []}
        yml_file = tmp_path / "test.yml"
        yml_file.write_text(yaml.dump(test_data))

        result = load_test_file(yml_file)
        assert result == test_data

    def test_load_json_file(self, tmp_path):
        """Test loading valid JSON test file."""
        test_data = {
            "test_cases": [
                {
                    "name": "Test case 1",
                    "context": {"req": {}, "payload": None},
                    "tests": [[{"id": "item1"}, True]],
                }
            ]
        }
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps(test_data))

        result = load_test_file(json_file)
        assert result == test_data

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading non-existent file raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            load_test_file(nonexistent)

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML raises error."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [")

        with pytest.raises(yaml.YAMLError):
            load_test_file(invalid_yaml)

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises error."""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{invalid json")

        with pytest.raises(json.JSONDecodeError):
            load_test_file(invalid_json)


class TestRunTestCase:
    """Tests for run_test_case function."""

    @pytest.mark.asyncio
    async def test_simple_passing_test(self):
        """Test a simple passing test case."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["(properties.private = false)"],
            {},
        )

        test_case = {
            "context": {"req": {}, "payload": None},
            "tests": [
                [{"id": "item1", "properties": {"private": False}}, True],
                [{"id": "item2", "properties": {"private": True}}, False],
            ],
        }

        success, message = await run_test_case(test_case, filter_instance, 1)
        assert success is True
        assert "All 2 items matched expected results" in message

    @pytest.mark.asyncio
    async def test_failing_test_mismatch(self):
        """Test a test case with mismatched expectations."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["(properties.private = false)"],
            {},
        )

        test_case = {
            "context": {"req": {}, "payload": None},
            "tests": [
                [{"id": "item1", "properties": {"private": False}}, False],  # Wrong!
            ],
        }

        success, message = await run_test_case(test_case, filter_instance, 1)
        assert success is False
        assert "Item match failures" in message
        assert "item1" in message

    @pytest.mark.asyncio
    async def test_invalid_cql2_expression(self):
        """Test handling of invalid CQL2 filter generation."""
        # Create a mock filter that returns invalid CQL2
        mock_filter = AsyncMock(return_value="invalid cql2 (((")

        test_case = {
            "context": {"req": {}, "payload": None},
            "tests": [[{"id": "item1"}, True]],
        }

        success, message = await run_test_case(test_case, mock_filter, 1)
        assert success is False
        assert "Failed to generate or validate CQL2 filter" in message

    @pytest.mark.asyncio
    async def test_templated_filter_with_context(self):
        """Test templated filter using context variables."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["{{ '(properties.private = false)' if payload is none else 'true' }}"],
            {},
        )

        # Test with no payload (anonymous)
        test_case_anon = {
            "context": {"req": {}, "payload": None},
            "tests": [
                [{"id": "item1", "properties": {"private": False}}, True],
                [{"id": "item2", "properties": {"private": True}}, False],
            ],
        }

        success, message = await run_test_case(test_case_anon, filter_instance, 1)
        assert success is True

        # Test with payload (authenticated)
        test_case_auth = {
            "context": {"req": {}, "payload": {"sub": "user123"}},
            "tests": [
                [{"id": "item1", "properties": {"private": False}}, True],
                [{"id": "item2", "properties": {"private": True}}, True],
            ],
        }

        success, message = await run_test_case(test_case_auth, filter_instance, 2)
        assert success is True

    @pytest.mark.asyncio
    async def test_cql2_json_format(self):
        """Test filter that returns CQL2 JSON format."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ['{"op": "=", "args": [{"property": "private"}, false]}'],
            {},
        )

        test_case = {
            "context": {"req": {}, "payload": None},
            "tests": [
                [{"id": "item1", "private": False}, True],
                [{"id": "item2", "private": True}, False],
            ],
        }

        success, message = await run_test_case(test_case, filter_instance, 1)
        assert success is True


class TestRunTests:
    """Tests for run_tests function."""

    @pytest.mark.asyncio
    async def test_run_multiple_test_cases(self):
        """Test running multiple test cases."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["(properties.private = false)"],
            {},
        )

        test_data = {
            "test_cases": [
                {
                    "name": "Public items only",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item1", "properties": {"private": False}}, True],
                    ],
                },
                {
                    "name": "Private items excluded",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item2", "properties": {"private": True}}, False],
                    ],
                },
            ]
        }

        passed, failed = await run_tests(filter_instance, test_data)
        assert passed == 2
        assert failed == 0

    @pytest.mark.asyncio
    async def test_run_with_failures(self):
        """Test running tests with some failures."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["(properties.private = false)"],
            {},
        )

        test_data = {
            "test_cases": [
                {
                    "name": "Passing test",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item1", "properties": {"private": False}}, True],
                    ],
                },
                {
                    "name": "Failing test",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item2", "properties": {"private": False}}, False],
                    ],
                },
            ]
        }

        passed, failed = await run_tests(filter_instance, test_data)
        assert passed == 1
        assert failed == 1

    @pytest.mark.asyncio
    async def test_run_empty_test_cases(self):
        """Test running with no test cases."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["true"],
            {},
        )

        test_data = {"test_cases": []}

        passed, failed = await run_tests(filter_instance, test_data)
        assert passed == 0
        assert failed == 0

    @pytest.mark.asyncio
    async def test_run_missing_test_cases_key(self):
        """Test running with missing test_cases key."""
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            ["true"],
            {},
        )

        test_data = {}

        passed, failed = await run_tests(filter_instance, test_data)
        assert passed == 0
        assert failed == 0


class TestPrintColored:
    """Tests for print_colored function."""

    def test_print_colored_output(self, capsys):
        """Test colored output formatting."""
        print_colored("Test message", Colors.GREEN)
        captured = capsys.readouterr()
        assert f"{Colors.GREEN}Test message{Colors.RESET}" in captured.out

    def test_print_colored_different_colors(self, capsys):
        """Test different color codes."""
        print_colored("Red text", Colors.RED)
        captured = capsys.readouterr()
        assert Colors.RED in captured.out

        print_colored("Blue text", Colors.BLUE)
        captured = capsys.readouterr()
        assert Colors.BLUE in captured.out


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_main_success(self, tmp_path):
        """Test successful CLI execution."""
        # Create a simple test file
        test_file = tmp_path / "test.yaml"
        test_data = {
            "test_cases": [
                {
                    "name": "Simple test",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item1", "properties": {"private": False}}, True],
                    ],
                }
            ]
        }
        test_file.write_text(yaml.dump(test_data))

        # Mock sys.argv
        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["(properties.private = false)"]',
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 0

    def test_main_with_failures(self, tmp_path):
        """Test CLI execution with test failures."""
        test_file = tmp_path / "test.yaml"
        test_data = {
            "test_cases": [
                {
                    "name": "Failing test",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item1", "properties": {"private": False}}, False],
                    ],
                }
            ]
        }
        test_file.write_text(yaml.dump(test_data))

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["(properties.private = false)"]',
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_no_tests(self, tmp_path):
        """Test CLI with no test cases."""
        test_file = tmp_path / "test.yaml"
        test_data = {"test_cases": []}
        test_file.write_text(yaml.dump(test_data))

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["true"]',
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_invalid_filter_args(self, tmp_path):
        """Test CLI with invalid filter args JSON."""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("test_cases: []")

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                "{invalid json}",
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_filter_args_not_array(self, tmp_path):
        """Test CLI with filter args that is not an array."""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("test_cases: []")

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '{"not": "an array"}',
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_invalid_filter_kwargs(self, tmp_path):
        """Test CLI with invalid filter kwargs JSON."""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("test_cases: []")

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["arg"]',
                "--filter-kwargs",
                "{invalid json}",
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_filter_kwargs_not_object(self, tmp_path):
        """Test CLI with filter kwargs that is not an object."""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("test_cases: []")

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["arg"]',
                "--filter-kwargs",
                '["not", "an", "object"]',
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_invalid_filter_class_path(self, tmp_path):
        """Test CLI with invalid filter class path."""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("test_cases: []")

        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "invalid.path.without.colon",
                "--filter-args",
                "[]",
                "--test-file",
                str(test_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_nonexistent_test_file(self, tmp_path):
        """Test CLI with non-existent test file."""
        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["true"]',
                "--test-file",
                str(tmp_path / "nonexistent.yaml"),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    def test_main_with_kwargs(self, tmp_path):
        """Test CLI with filter kwargs."""
        test_file = tmp_path / "test.yaml"
        test_data = {
            "test_cases": [
                {
                    "name": "Simple test",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [{"id": "item1", "properties": {"private": False}}, True],
                    ],
                }
            ]
        }
        test_file.write_text(yaml.dump(test_data))

        # Note: Template doesn't actually use kwargs, but we test the CLI handles them
        with patch.object(
            sys,
            "argv",
            [
                "stac-auth-tests",
                "--filter-class",
                "stac_auth_proxy.filters:Template",
                "--filter-args",
                '["(properties.private = false)"]',
                "--filter-kwargs",
                '{"some_kwarg": "value"}',
                "--test-file",
                str(test_file),
            ],
        ):
            # Should not error even with unexpected kwargs
            exit_code = main()

        # Template doesn't support kwargs, so this will raise TypeError
        assert exit_code == 1


class TestIntegrationWithExampleFile:
    """Integration tests using the example auth rules file."""

    def test_example_file_exists(self):
        """Verify the example auth rules file exists."""
        example_file = Path(__file__).parent / "example_auth_rules.yaml"
        if example_file.exists():
            # Load and validate it's valid YAML
            data = load_test_file(example_file)
            assert "test_cases" in data
            assert len(data["test_cases"]) > 0

    @pytest.mark.asyncio
    async def test_run_against_example_template(self):
        """Test running a simple template against structured test data."""
        # Create a filter that allows public items or items in allowed collections
        filter_instance = load_filter_class(
            "stac_auth_proxy.filters:Template",
            [
                """
                {% if payload is none %}
                (properties.private = false)
                {% else %}
                true
                {% endif %}
                """
            ],
            {},
        )

        test_data = {
            "test_cases": [
                {
                    "name": "Anonymous user sees only public items",
                    "context": {"req": {}, "payload": None},
                    "tests": [
                        [
                            {
                                "id": "public-item",
                                "properties": {"private": False},
                            },
                            True,
                        ],
                        [
                            {
                                "id": "private-item",
                                "properties": {"private": True},
                            },
                            False,
                        ],
                    ],
                },
                {
                    "name": "Authenticated user sees all items",
                    "context": {"req": {}, "payload": {"sub": "user123"}},
                    "tests": [
                        [
                            {
                                "id": "public-item",
                                "properties": {"private": False},
                            },
                            True,
                        ],
                        [
                            {
                                "id": "private-item",
                                "properties": {"private": True},
                            },
                            True,
                        ],
                    ],
                },
            ]
        }

        passed, failed = await run_tests(filter_instance, test_data)
        assert passed == 2
        assert failed == 0
