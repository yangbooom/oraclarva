"""Strict schema and tolerant finite-float comparison for JSON artifacts."""

from __future__ import annotations

from math import isfinite
from typing import Any


NUMERIC_TOLERANCE = 1e-8


def first_mismatch(expected: Any, actual: Any, path: str = "$") -> str | None:
    """Return the first schema/value mismatch in two JSON-compatible trees."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return None if expected is actual else f"{path}: boolean mismatch"
    if isinstance(expected, int) or isinstance(actual, int):
        return (
            None
            if type(expected) is type(actual) and expected == actual
            else f"{path}: integer/type mismatch"
        )
    if isinstance(expected, float) or isinstance(actual, float):
        if not isinstance(expected, float) or not isinstance(actual, float):
            return f"{path}: numeric type mismatch"
        if not isfinite(expected) or not isfinite(actual):
            return f"{path}: non-finite numeric value"
        if abs(expected - actual) > NUMERIC_TOLERANCE:
            return f"{path}: {expected} != {actual}"
        return None
    if isinstance(expected, dict) or isinstance(actual, dict):
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            return f"{path}: object type mismatch"
        if expected.keys() != actual.keys():
            return f"{path}: object keys mismatch"
        for key in expected:
            mismatch = first_mismatch(
                expected[key], actual[key], f"{path}.{key}"
            )
            if mismatch:
                return mismatch
        return None
    if isinstance(expected, list) or isinstance(actual, list):
        if not isinstance(expected, list) or not isinstance(actual, list):
            return f"{path}: array type mismatch"
        if len(expected) != len(actual):
            return f"{path}: array length mismatch"
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual, strict=True)
        ):
            mismatch = first_mismatch(
                expected_item, actual_item, f"{path}[{index}]"
            )
            if mismatch:
                return mismatch
        return None
    return None if expected == actual else f"{path}: value mismatch"
