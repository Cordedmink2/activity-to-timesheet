"""The failure classes of the provider contract (§ 4), as exceptions.

An adapter raises one of these and the dispatcher maps it onto the exit code. The numbers
are the contract's; which provider response means which class is the adapter's (§ 6.2).
"""
from __future__ import annotations


class ProviderError(Exception):
    """Base class. `exit_code` is the contract's number for the class."""
    exit_code = 1


class Usage(ProviderError):
    """An argument the contract refuses. The provider was not asked anything."""
    exit_code = 2


class Misconfigured(ProviderError):
    """A setting the adapter needs is absent: a credential, the workspace, the zone."""
    exit_code = 3


class Refused(ProviderError):
    """The provider, or the adapter's pre-flight check for it, rejected a well-formed request."""
    exit_code = 4


class Unreachable(ProviderError):
    """No answer: a network error, a timeout. Nothing was decided by the provider."""
    exit_code = 5


class NoMatch(ProviderError):
    """`lookup` completed both reads and found nothing; `refresh --wait` timed out."""
    exit_code = 6
