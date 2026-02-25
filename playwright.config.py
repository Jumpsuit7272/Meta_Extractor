"""Playwright configuration for E2E tests."""

# Run with: playwright install && pytest tests/e2e -v
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the RPD API (default: http://localhost:8000)",
    )
