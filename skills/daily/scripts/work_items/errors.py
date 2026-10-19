"""Failure classes of the work-item boundary, numbered as the provider contract numbers
the same causes (§ 4) so a caller reads one set of exit codes."""
from __future__ import annotations


class WorkItemError(Exception):
    exit_code = 1


class Misconfigured(WorkItemError):
    """A setting the source needs is absent, unknown or in the old shape."""
    exit_code = 3


class Refused(WorkItemError):
    """The source, or the tool in front of it, answered and the answer is not a catalog."""
    exit_code = 4
