class AnalyzerError(Exception):
    """Base exception with a CLI-friendly exit code."""

    exit_code = 3


class UsageError(AnalyzerError):
    exit_code = 2


class DependencyError(AnalyzerError):
    exit_code = 3


class AnalysisError(AnalyzerError):
    exit_code = 3
