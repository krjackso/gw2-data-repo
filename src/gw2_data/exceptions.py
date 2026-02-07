"""
Custom exceptions for GW2 data extraction.

Provides specific error types for different failure modes to enable
better error handling and debugging.
"""


class GW2DataError(Exception):
    pass


class APIError(GW2DataError):
    pass


class WikiError(GW2DataError):
    pass


class ValidationError(GW2DataError):
    pass


class ExtractionError(GW2DataError):
    pass
