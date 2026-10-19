"""The Harvest adapter behind the provider contract (docs/provider-contract.md § 6.2).

Everything Harvest-shaped is in this package - its endpoints, field names, headers, paging,
status codes, catalog files and the daylight-saving guard - and nothing above it reads any of
that. The dispatcher imports this package by the name `TIMESHEET_PROVIDER` selects and calls
the interface below. Importing it resolves no credential and writes nothing to the
environment.

    NAME
    check_post(body) / check_patch(entry_id, fields)   read-only; raise Refused / ...
    post(body) / patch(entry_id, fields)               called only on a confirmed run
    lookup(query, task, catalog_dir, cache_only, days)
    list_entries(date_from, date_to)
    refresh(wait_for, attempts, delay)
    catalog_age()
"""
from provider.harvest.catalog import catalog_age, lookup, refresh
from provider.harvest.entries import check_patch, check_post, list_entries, patch, post

NAME = "harvest"

__all__ = ["NAME", "check_post", "check_patch", "post", "patch", "lookup", "list_entries",
           "refresh", "catalog_age"]
