"""The fixture builders emit the exact bucket and event shapes the real watchers write
(guided-setup T21, US-2/AC-2, US-3/AC-3, D10).

Sources, read at the pinned ActivityWatch v0.14.1 submodule commits:
  aw-watcher-window c8814e4  aw_watcher_window/main.py
      L183  bucket id  f"{client.client_name}_{client.client_hostname}" -> aw-watcher-window_<host>
      L184  event type "currentwindow"
      L376  Event(timestamp=now, data=current_window) -> data keys `app` and `title`
  aw-watcher-afk 5aaab74     aw_watcher_afk/afk.py
      L52-54 bucket id  "{}_{}".format(client_name, client_hostname) -> aw-watcher-afk_<host>
      L60-61 data {"status": "afk" | "not-afk"}, Event(timestamp, duration, data)
      L71   event type "afkstatus"
"""
import datetime as dt

from scenarios import CONTEXT_ACME_BETA, real_shape_buckets, week_of_work
from support import iso_z


def test_the_window_bucket_id_and_event_data_keys_are_the_watchers():
    buckets = real_shape_buckets(week_of_work(1)[0])
    assert "aw-watcher-window_example-host" in buckets
    for event in buckets["aw-watcher-window_example-host"]:
        assert set(event["data"]) == {"app", "title"}


def test_the_afk_bucket_id_and_status_values_are_the_watchers():
    buckets = real_shape_buckets(week_of_work(1)[0])
    events = buckets["aw-watcher-afk_example-host"]
    assert events and {e["data"]["status"] for e in events} <= {"afk", "not-afk"}
    assert all(set(e["data"]) == {"status"} for e in events)


def test_events_carry_an_iso_utc_timestamp_and_a_numeric_duration_in_seconds():
    for events in real_shape_buckets(week_of_work(1)[0]).values():
        for e in events:
            assert set(e) == {"timestamp", "duration", "data"}
            assert e["timestamp"].endswith("Z") and isinstance(e["duration"], (int, float))
            dt.datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            assert e["duration"] > 0


def test_a_week_is_five_distinct_past_weekdays_with_acme_and_beta_titles_and_example_hosts():
    days = week_of_work(5)
    assert len({d.date for d in days}) == 5 and all(d.date.weekday() < 5 for d in days)
    titles = " ".join(e["data"]["title"] for d in days for e in d.window_events())
    assert "ACME" in titles and "BETA" in titles
    assert all(d.host.startswith("example") for d in days)
    assert iso_z  # builders use the one shared timestamp formatter


def test_the_context_file_has_one_section_per_client_and_a_category_terms_line_each():
    assert CONTEXT_ACME_BETA.count("**Category terms**") == 2
    assert "ACME" in CONTEXT_ACME_BETA and "BETA" in CONTEXT_ACME_BETA


def test_a_browser_title_has_the_url_in_title_extensions_shape_and_the_scripts_read_its_host():
    """The extension writes `{title}-{hostname}{path}` (the format setup step 3 tells the user
    to save), so the host is joined to the page title by a bare hyphen. The category script
    must read `example.invalid` out of the fixture's own browser title."""
    import category_rules
    sample = [(e["data"]["app"], e["data"]["title"])
              for d in week_of_work(2) for e in d.window_events()]
    assert category_rules.host_counts(sample)["example.invalid"] >= 1
