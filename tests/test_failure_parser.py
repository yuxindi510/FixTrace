from fixtrace.services.failure_parser import PytestFailureParser


def test_parses_pytest_summary_and_location() -> None:
    output = """
E       AssertionError: assert 120 == 80
tests/test_calculator.py:5: AssertionError
FAILED tests/test_calculator.py::test_twenty_percent_discount - AssertionError: assert 120 == 80
"""

    failures = PytestFailureParser().parse(output)

    assert len(failures) == 1
    assert failures[0].test_id == "tests/test_calculator.py::test_twenty_percent_discount"
    assert failures[0].line == 5
    assert failures[0].exception_type == "AssertionError"


def test_parses_collection_error_without_failed_summary() -> None:
    output = """
tests/test_import.py:2: in <module>
E   ModuleNotFoundError: No module named 'missing_package'
"""

    failures = PytestFailureParser().parse(output)

    assert failures[0].test_id == "collection-or-runtime"
    assert failures[0].exception_type == "ModuleNotFoundError"
