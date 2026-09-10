"""Guards on the configuration surface the manifest declares, and on the bridge to it.

A fresh install asks the user for their own facts once. The manifest's `userConfig` block
is where that question is written down: what is asked, what is optional, and what the
harness must keep out of a file. Getting it wrong fails in ways no script-level test can
see — a required field left optional means an install that completes and a run that
doesn't; a credential not marked sensitive means a token written into `settings.json` in
plaintext; a default baked into the timezone means someone else's day silently dated in
New Zealand.

The other half is the bridge. The harness injects the declared values as
`CLAUDE_PLUGIN_OPTION_<KEY>` into *hook* processes only, so `hooks/publish_plugin_config.py`
republishes them through `$CLAUDE_ENV_FILE` — which reaches the scripts the model runs
through the **Bash** tool, and no others. The assertions below are on the shapes that make
that round-trip exact and the quoting that makes it safe; the platform's own behaviour was
verified empirically against the installed CLI rather than asserted from a reading of it,
including the scope: a fragment published by a hook was read back as set in a Bash tool
call and unset in a PowerShell one, in the same session.

Nothing here can hold that scope — it is the harness's behaviour, not this repo's. What
the repo holds instead is the skills directing every read of a configured value through
Bash, and `skill_config.note_for_an_unreached_shell()` naming the shell when a command
gets through regardless; `docs/skills/daily/decision-log.md` § "Two ways the configuration does not
arrive" carries the evidence and the rejected alternatives.
"""

import importlib.util
import json
import os
import re
import subprocess

import pytest

from shipped import REPO

# The wrapper is a POSIX shell script, so driving it needs a shell that can run one.
# Imported from the sibling suite rather than copied: `find_bash()` there picks Git Bash
# specifically, because `System32\bash.exe` on Windows is the WSL launcher and would run
# the script in a different filesystem namespace entirely. A second copy of that reasoning
# is a second thing to get wrong.
from test_install_scripts import bash, posix, requires_bash  # noqa: E402

PLUGIN_MANIFEST = REPO / ".claude-plugin" / "plugin.json"
HOOKS = REPO / "hooks"
README = REPO / "README.md"

# What must be asked for, because nothing can run without it.
REQUIRED = {"HARVEST_ACCOUNT_ID", "HARVEST_API_KEY"}
# What the harness must keep out of `settings.json` and out of the plugin folder.
SENSITIVE = {"HARVEST_ACCOUNT_ID", "HARVEST_API_KEY"}
# What a user can leave blank and still complete a run. The timezone joined this set with
# #30: blank means the machine's own zone, announced as such on every run — a fallback that
# lives in the scripts, like every other one here, and not a manifest `default`.
OPTIONAL = {"TIMESHEET_TIMEZONE", "TIMESHEET_ACTIVITY_URL", "TIMESHEET_SCREENSHOTS_DIR",
            "TIMESHEET_WORKSPACE", "TIMESHEET_OUTLOOK_CALENDAR"}

# The export has no manifest to be asked from, so the same keys go in a `.env` copied from
# this template. The two are the same declaration made twice, which is why a test holds them
# together below.
ENV_TEMPLATE = REPO / "skills" / "daily" / ".env.example"

# Keys the template carries that the manifest deliberately does not: the work-item source's.
# They belong to one org rather than to every install, so the configure dialog never asks
# for them (README § "Coming from a hand-installed copy"), and drawing that boundary
# properly is #37's. Named here so that *any other* difference between the two fails.
WORK_ITEM_SOURCE_KEYS = {"DATAVERSE_URL", "PAC_AUTH_PROFILE"}


def user_config() -> dict:
    return json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))["userConfig"]


def load_publisher():
    """`hooks/publish_plugin_config.py`, imported by path.

    It is a hook script, not a package member — the harness runs it by path and nothing
    imports it — so there is no module to import by name.
    """
    path = HOOKS / "publish_plugin_config.py"
    spec = importlib.util.spec_from_file_location("publish_plugin_config", path)
    assert spec and spec.loader, f"{path} is not importable as a module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_skill_config():
    """The `daily` skill's `skill_config`, imported by path.

    By path rather than by adding `scripts/` to `sys.path`: this is a repo-level suite
    with no skill on its import path, and putting one there would let a later test import
    a bundled module by accident and read the real `.env` through it.
    """
    path = REPO / "skills" / "daily" / "scripts" / "skill_config.py"
    spec = importlib.util.spec_from_file_location("skill_config_under_test", path)
    assert spec and spec.loader, f"{path} is not importable as a module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load_publisher()


# --------------------------------------------------------------------------------------
# What the install asks for
# --------------------------------------------------------------------------------------

def test_the_declared_surface_is_exactly_the_settings_the_scripts_resolve():
    """The manifest is the single declaration. An option nobody reads is a question asked
    for nothing; a setting nobody declares is a question never asked, and the user meets it
    as a failed run instead."""
    assert set(user_config()) == REQUIRED | OPTIONAL


def test_every_value_without_which_nothing_runs_is_required():
    """`required` is what makes the install *prompt*. Left off, the install completes and
    the first run is the thing that fails — at which point the user has no dialog to go
    back to, only an error naming a key."""
    asked = {k for k, opt in user_config().items() if opt.get("required")}
    assert asked == REQUIRED


def test_everything_else_is_skipped_at_install_time():
    """AC: "a user who sets nothing optional can still complete a run". Each of these has a
    working fallback in the scripts — localhost, `~/Pictures/WorkScreenshots`, the current
    directory — so asking for it would be asking a new user to answer a question they have
    no basis to answer yet."""
    for key in OPTIONAL:
        assert not user_config()[key].get("required"), f"{key} is asked for but need not be"


def test_the_credentials_are_the_sensitive_fields_and_nothing_else_is():
    """`sensitive` is what keeps a value out of `settings.json`.

    Verified empirically against the installed CLI: a non-sensitive option lands in
    `~/.claude/settings.json` under `pluginConfigs`, a sensitive one does not appear there
    at all — it goes to the harness's own credential store (the OS keychain on macOS,
    `~/.claude/.credentials.json` elsewhere; the docs say which, because this plugin is
    Windows-first and a flat "keychain" would be wrong for most of its users).

    So this flag is the whole of AC "provider credentials are stored by the harness, not
    written to a file in the plugin" — there is no second mechanism to also set.

    Asserting equality, not containment: marking a path or a URL sensitive would hide it
    from the user's own `settings.json` for no benefit, and make a wrong value unreadable
    at exactly the moment they are trying to see what they typed.
    """
    marked = {k for k, opt in user_config().items() if opt.get("sensitive")}
    assert marked == SENSITIVE


def test_no_option_carries_a_default():
    """AC: "no New Zealand default is silently applied to a new user's data".

    Two reasons, and the second is the load-bearing one. A timezone default would date
    another user's timesheet in the wrong day. And a manifest `default` is only a *dialog
    pre-fill* — verified empirically: an optional option the user never set is not injected
    into the hook environment at all, default or no default. So a default here would not
    even reach the scripts; it would only put a value in front of a user as though it were
    the considered answer for them. The real fallbacks live in the scripts, at the
    `setting(..., default=...)` call that documents each one.
    """
    with_defaults = {k for k, opt in user_config().items() if "default" in opt}
    assert not with_defaults, f"a default is declared for: {sorted(with_defaults)}"


@pytest.mark.parametrize("key", sorted(REQUIRED | OPTIONAL))
def test_every_option_says_what_it_is_and_where_to_get_it(key):
    """The dialog shows the title and description and nothing else. A user filling in
    `HARVEST_ACCOUNT_ID` needs the URL it is printed at, not a restatement of the key."""
    opt = user_config()[key]
    assert opt.get("title"), f"{key} has no title"
    assert len(opt.get("description", "")) > 30, f"{key}'s description does not say enough"


# The one sentence every optional description ends with (#49, story 21), and two deviations
# from the spec's literal "Not sure? Leave blank and run /setup.", both forced by what the
# dialog actually is. `/billables:setup` because that is the command this plugin registers,
# and a dialog naming a command the harness has no such thing for sends the user nowhere.
# "Leave it as it is" because one of the four optional settings is a *boolean* — a checkbox
# with no blank to leave — and one sentence that is true of a text box, a directory picker
# and a checkbox is worth more than the spec's word for the three of them it fits. The
# export's `.env.example` says "blank", where the value really is a blank line.
SETUP_SENTENCE = "Not sure? Leave it as it is and run /billables:setup."


@pytest.mark.parametrize("key", sorted(OPTIONAL))
def test_every_optional_description_says_where_to_learn_what_it_does(key):
    """An optional setting is one a user can answer wrongly by guessing at it.

    The dialog is the whole of what they have to go on — a title, a description, and no
    room for the paragraph each of these actually needs. So each one ends by naming the
    place where the explanation is a walkthrough rather than a sentence: the `setup` skill,
    which enters every optional setting's step whether it is filled in or not. One sentence,
    the same sentence, because a user reading four descriptions should recognise the offer
    on the second one rather than read it as four different offers.
    """
    description = user_config()[key]["description"].rstrip()
    assert description.endswith(SETUP_SENTENCE), (
        f"{key}'s description does not end with {SETUP_SENTENCE!r}, so a user who does not "
        f"know what it does has nowhere to be sent:\n{description}")


@pytest.mark.parametrize("key", sorted(REQUIRED))
def test_a_required_setting_is_never_offered_as_one_to_leave_blank(key):
    """The same sentence on a required key would be advice to skip a value nothing runs
    without — and the install prompts for these, so there is no blank to leave."""
    assert SETUP_SENTENCE not in user_config()[key]["description"], (
        f"{key} is required, so telling the user they may leave it blank is wrong")


def test_the_workspace_description_says_what_the_folder_holds_in_plain_words():
    """The one description written for someone who already knew the answer (#49, story 22).

    It used to name `Timesheets/` and "the `.mcp/` catalogs" — two words for things that do
    not exist yet at the moment the dialog asks, on a machine where nothing has run. A
    first-time installer cannot decide whether to leave a folder blank when what would go
    in it is described by the name of a folder they have never seen. The catalogs are a
    cache of their projects and tasks, and that is sayable without the word.
    """
    description = user_config()["TIMESHEET_WORKSPACE"]["description"]
    jargon = [word for word in ("catalog", ".mcp") if word in description.lower()]
    assert not jargon, (
        f"the workspace description assumes the reader knows what {', '.join(jargon)} "
        f"means, at the one moment they cannot:\n{description}")
    assert "Timesheets" in description, (
        "the workspace description never names the folder the user will actually see in "
        f"there, which is the whole of what it is for:\n{description}")


def test_the_calendar_toggle_is_a_boolean_with_nothing_to_type():
    """One on/off switch, no magic word (#49, story 19). A string option would have the
    dialog ask for text and the user guess at `true`, `yes`, `on` — of which the seam
    accepts exactly one, so two of the three would be a calendar silently left off."""
    assert user_config()["TIMESHEET_OUTLOOK_CALENDAR"]["type"] == "boolean"


def template_lines() -> dict[str, str]:
    """`KEY` -> value for every assignment line in the export's env template."""
    text = ENV_TEMPLATE.read_text(encoding="utf-8")
    return {m.group(1): m.group(2)
            for m in re.finditer(r"^([A-Z][A-Z0-9_]*)=(.*)$", text, re.M)}


def test_the_env_template_names_exactly_the_keys_the_manifest_declares():
    """Two install routes, one configuration. A key declared in the manifest and missing
    from the template is a setting the exported install has no line for — its user reads
    the plugin's setup instructions, finds no such key in the file they were told to fill
    in, and the feature stays off with nothing saying why. The other direction is a key the
    template offers that nothing resolves."""
    assert set(template_lines()) == set(user_config()) | WORK_ITEM_SOURCE_KEYS, (
        "the export's .env.example and the manifest's userConfig name different keys")


# The export's copy of the sentence above. "Blank" is the right word here and the wrong one
# in the dialog: a `.env` line really is left blank, and there is no `/billables:setup`
# command on a harness that has no plugins — the skill is invoked by whatever that harness
# calls a skill.
TEMPLATE_SENTENCE = "Not sure? Leave it blank and run the setup skill."


def template_comment(key: str) -> str:
    """The comment block sitting directly above `KEY=` in the export's env template.

    That block is the export route's whole equivalent of the dialog's description — there
    is no dialog to read one from — so it is what story 21 has to hold on this route.
    """
    lines = ENV_TEMPLATE.read_text(encoding="utf-8").splitlines()
    at = next((i for i, line in enumerate(lines) if line.startswith(f"{key}=")), None)
    assert at is not None, f"{key} has no line in the env template"
    block = []
    while at and lines[at - 1].startswith("#"):
        at -= 1
        block.insert(0, lines[at].lstrip("# ").rstrip())
    return "\n".join(block)


@pytest.mark.parametrize("key", sorted(OPTIONAL))
def test_the_export_route_offers_the_same_walkthrough_the_dialog_does(key):
    """Two install routes, one configuration — and one of them has no dialog to be asked
    from, only this file. A user copying the template reads these comments in place of the
    descriptions, so an offer made in the manifest and not here is an offer half the
    installs never get."""
    block = template_comment(key)
    assert block.rstrip().endswith(TEMPLATE_SENTENCE), (
        f"{key}'s comment in the env template does not end with {TEMPLATE_SENTENCE!r}, so "
        f"the exported install's reader is not told where the explanation is:\n{block}")


def test_the_export_route_explains_the_workspace_without_the_catalogs_either():
    """The same rewrite as the manifest's (#49, story 22), on the copy the export reads.

    This one was the *source* of the jargon — "where the skill keeps its `.mcp/` catalogs"
    — and rewriting the manifest alone would have left the two descriptions of one setting
    disagreeing about what the folder is for.
    """
    block = template_comment("TIMESHEET_WORKSPACE")
    jargon = [word for word in ("catalog", ".mcp/ ") if word in block.lower()]
    assert not jargon, (
        f"the env template still describes the workspace as {', '.join(jargon)}:\n{block}")


def test_every_template_key_is_present_and_blank():
    """The template is copied to `.env` and filled in. A value already in it is a default
    by another name, and `test_no_option_carries_a_default` says why there are none."""
    filled = {k: v for k, v in template_lines().items() if v.strip()}
    assert not filled, f"the env template pre-fills: {filled}"


def test_the_two_directories_are_declared_as_directories():
    """`type: "directory"` gives the dialog a picker. It does *not* validate that the path
    exists — verified empirically: `C:/does/not/exist/at/all` was accepted and stored. So
    the type is for the user's convenience, and every consumer of these two still has to
    handle a path that isn't there."""
    cfg = user_config()
    assert cfg["TIMESHEET_SCREENSHOTS_DIR"]["type"] == "directory"
    assert cfg["TIMESHEET_WORKSPACE"]["type"] == "directory"


# --------------------------------------------------------------------------------------
# The round-trip to the scripts
# --------------------------------------------------------------------------------------

IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]*$")


@pytest.mark.parametrize("key", sorted(REQUIRED | OPTIONAL))
def test_every_option_key_survives_the_round_trip_to_a_variable_name(key):
    """The option key *is* the setting key the scripts ask `setting()` for.

    The harness derives the injected variable name by upper-casing the key and replacing
    anything outside `[A-Za-z0-9_]` with `_`. That is lossy: a key declared as
    `harvest.api-key` arrives as `HARVEST_API_KEY`, and stripping the prefix back would
    recover a name no script resolves — silently, with the value simply absent. Declaring
    every key as an already-upper-case identifier makes the derivation the identity.
    """
    assert IDENTIFIER.match(key), f"{key} would not round-trip through the harness's naming"


def test_a_session_start_hook_publishes_the_configuration():
    """Without this the declared values reach hook processes and stop there. The manifest
    entry and the two files it names are one mechanism; a missing file is a session that
    starts fine and a skill that behaves as though nothing was ever configured."""
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    commands = [h["command"]
                for group in manifest["hooks"]["SessionStart"]
                for h in group["hooks"]]
    assert any("publish_plugin_config.sh" in c for c in commands), commands
    assert (HOOKS / "publish_plugin_config.sh").is_file()
    assert (HOOKS / "publish_plugin_config.py").is_file()


def install_section() -> str:
    """The README's `## Install` block — the text a user reads before they install.

    Scoped to that section rather than the whole file: this repo's README also documents
    migrating an older hand install and the exported route, both of which mention scopes
    of their own, and a passing mention down there is not the instruction anyone follows.
    """
    match = re.search(r"^## Install\n(.*?)(?=^## |\Z)", README.read_text(encoding="utf-8"),
                      re.M | re.S)
    assert match, "README.md has no `## Install` section"
    return match.group(1)


def test_the_install_instruction_names_the_scope_that_publishes_everywhere():
    """Every guard in this file is downstream of the plugin being *enabled where you are*.

    A plugin installed at **local** scope is bound to the one directory it was installed
    from. Start a session anywhere else and it is simply disabled there: no SessionStart
    hook is registered, so nothing publishes the fragment, so every script reports the
    configuration missing however carefully the user filled the dialog in. The manifest,
    the round-trip and the quoting are all exactly right and none of them run.

    That is not hypothetical. Diagnosed on 2026-09-02: an install made from `~/Admin`
    landed at local scope and bound itself to that directory, and a session started in a
    checkout beside it found no credentials in *either* shell —
    `installed_plugins.json` recorded `"scope": "local", "projectPath": ".../Admin"` and
    `claude plugin list` reported `disabled`, while the two causes the error offered were
    both already satisfied.

    `claude plugin install` defaults to user scope, so the CLI route is safe by default
    and the interactive one is what needs saying. The section therefore has to name the
    scope to pick, what the other one costs, and the command that shows which you got.
    """
    section = install_section()
    assert "user" in section and "scope" in section, (
        "the install instruction never names a scope, so whichever one the dialog "
        f"defaults to is the one the user gets:\n{section}")
    assert "local" in section, (
        "the install instruction does not say what a local-scope install costs — which "
        f"is a plugin that works in one directory and is disabled in every other:\n{section}")
    assert "claude plugin list" in section, (
        "nothing tells the user how to see which scope they ended up with:\n" + section)


def test_only_the_injected_options_are_published():
    """The bridge publishes what the harness injected and nothing else. It must not carry
    the rest of a hook process's environment into every command in the session."""
    got = publisher.option_values({
        "CLAUDE_PLUGIN_OPTION_TIMESHEET_TIMEZONE": "Europe/London",
        "PATH": "/usr/bin",
        "HARVEST_API_KEY": "not-ours-to-republish",
    })
    assert got == {"TIMESHEET_TIMEZONE": "Europe/London"}


def test_another_plugins_secret_is_never_republished():
    """The `CLAUDE_PLUGIN_OPTION_` prefix is the *harness's* namespace, not this plugin's.

    If a hook process is ever handed every enabled plugin's options, filtering on the
    prefix alone would export another plugin's sensitive value into the environment of
    every shell command for the rest of the session — where any subprocess, any `env`, and
    anything that logs its environment can read it. Intersecting against this manifest's
    declared keys makes the question moot rather than something to find out from a leak.
    """
    assert publisher.option_values({
        "CLAUDE_PLUGIN_OPTION_TIMESHEET_TIMEZONE": "Europe/London",
        "CLAUDE_PLUGIN_OPTION_SOME_OTHER_PLUGIN_TOKEN": "not-ours-to-republish",
    }) == {"TIMESHEET_TIMEZONE": "Europe/London"}


def test_the_declared_keys_are_read_from_the_manifest_beside_the_hook():
    """Read, not listed — so the filter cannot drift from the surface it filters against."""
    assert publisher.declared_keys() == REQUIRED | OPTIONAL


def test_an_unreadable_manifest_publishes_nothing_rather_than_everything(monkeypatch):
    """The safe direction. A manifest that cannot be read is not a licence to export
    whatever else happens to be in this process's environment."""
    monkeypatch.setattr(publisher, "MANIFEST", "no-such-manifest.json")
    assert publisher.declared_keys() == set()
    assert publisher.option_values(
        {"CLAUDE_PLUGIN_OPTION_TIMESHEET_TIMEZONE": "Europe/London"}) == {}


def test_a_blank_option_is_dropped_rather_than_published_as_empty():
    """`skill_config.has_value()` already treats blank as unset at every layer. Publishing
    `KEY=` would put an empty variable in front of that rule, and every later reader would
    have to know to ignore it."""
    assert publisher.option_values({
        "CLAUDE_PLUGIN_OPTION_TIMESHEET_ACTIVITY_URL": "",
        "CLAUDE_PLUGIN_OPTION_TIMESHEET_WORKSPACE": "   ",
    }) == {}


def test_a_value_with_a_quote_or_a_dollar_sign_arrives_unchanged():
    """These are a user's tokens and paths, and the fragment is sourced by a shell. An
    unescaped `$` or backtick would be expanded — a token silently truncated to whatever
    survived expansion, authenticating as nobody and failing with a 401 that names the
    wrong problem."""
    fragment = publisher.render({"HARVEST_API_KEY": "pt.$who`s`_it's-me"})
    assert fragment == "export HARVEST_API_KEY='pt.$who`s`_it'\\''s-me'\n"


def test_the_fragment_is_ordered_so_a_diff_of_it_means_a_value_changed():
    fragment = publisher.render({"B_KEY": "2", "A_KEY": "1"})
    assert fragment == "export A_KEY='1'\nexport B_KEY='2'\n"


def test_publishing_appends_to_the_file_the_harness_named(tmp_path, monkeypatch):
    """Appended, not truncated: the fragment is shared with every other hook publishing to
    this session, and a truncating write would take theirs out."""
    env_file = tmp_path / "sessionstart-hook-0.sh"
    env_file.write_bytes(b"export SOMETHING_ELSE='kept'\n")
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TIMESHEET_TIMEZONE", "Pacific/Auckland")

    assert publisher.main() == 0
    # Bytes, not text: `read_text` translates CRLF back to `\n`, so it cannot tell a shell
    # fragment from a Windows text file — which is exactly the mistake being pinned. The
    # shell that sources this strips a stray CR, but anything that *reads* the file rather
    # than sourcing it would carry the CR into the value.
    assert env_file.read_bytes() == (
        b"export SOMETHING_ELSE='kept'\n"
        b"export BILLABLES_CONFIG_PUBLISHED='1'\n"
        b"export TIMESHEET_TIMEZONE='Pacific/Auckland'\n")


def test_the_marker_the_scripts_look_for_is_the_one_the_hook_writes():
    """Two spellings of one name, and nothing else could hold them together.

    A hook is run by path, from a directory with no relationship to the skill, so it
    cannot import `skill_config` — the constant exists on both sides. A typo on either
    would not fail anything: the hook would publish a marker nobody reads, and every
    session would look to the scripts as though nothing had been published, so the note
    would fire on a machine where the values had in fact arrived. That is a wrong
    diagnosis attached to a message the user is already confused by.
    """
    assert publisher.MARKER == load_skill_config().PUBLISHED_MARK


def test_the_marker_is_the_only_thing_published_that_nobody_declared():
    """It is not a setting, so it is not in the manifest and `option_values()` never sees
    it. Asserting that keeps it from drifting into the declared surface, where
    `test_the_declared_surface_is_exactly_the_settings_the_scripts_resolve` would then
    demand a script resolve it."""
    assert publisher.MARKER not in user_config()
    assert publisher.option_values(
        {f"CLAUDE_PLUGIN_OPTION_{publisher.MARKER}": "1"}) == {}


@requires_bash
def test_a_candidate_that_exits_without_running_the_script_publishes_nothing_and_is_not_trusted(
        tmp_path):
    """The wrapper tries interpreters in turn, and an exit code is not evidence one ran.

    `python3` on Windows is frequently a shim in `WindowsApps` rather than an interpreter,
    and the wrapper exists to get past it — but it tests the wrong thing. `command -v`
    finds the shim, the shim exits, and `&& exit 0` accepts that as success: the loop stops
    at the first candidate that *returned* rather than the first that *worked*, and the
    session gets no configuration while the hook reports having published it. Every guard
    in this file passes, because none of this code ran.

    Observed on 2026-09-02: invoking `python3` on this machine handed control to the
    Python install manager, which updated itself and installed 3.14.7 — fifteen lines of
    installer output from a SessionStart hook. That one recovered and did run the script.
    A shim that simply exits does not, and nothing downstream can tell the difference.

    So the wrapper has to check the effect rather than the exit code. The publisher always
    writes at least the marker line, so a run that left the file untouched did not happen —
    which is a property of *this* wrapper and needs no third copy of the marker's spelling
    to assert.
    """
    env_file = tmp_path / "sessionstart-hook-0.sh"
    env_file.write_bytes(b"export SOMETHING_ELSE='kept'\n")
    stub = tmp_path / "stub"
    stub.mkdir()
    # A `python3` of the shape the wrapper is meant to survive: it prints a nag, runs
    # nothing, and exits 0.
    (stub / "python3").write_text(
        "#!/bin/sh\necho 'Python was not found; install it from the Microsoft Store'\nexit 0\n",
        encoding="utf-8", newline="\n")

    env = dict(os.environ)
    env["CLAUDE_ENV_FILE"] = str(env_file)
    env["CLAUDE_PLUGIN_OPTION_TIMESHEET_TIMEZONE"] = "Pacific/Auckland"
    # PATH is rewritten inside the shell, in POSIX form. Handing Git Bash a Windows-style
    # PATH through `env=` is the kind of thing that works until a path has a space in it.
    script = (f'chmod +x "{posix(stub)}/python3"; '
              f'PATH="{posix(stub)}:$PATH"; '
              f'exec sh "{posix(HOOKS / "publish_plugin_config.sh")}"')
    result = subprocess.run([bash(), "-c", script], env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")

    assert result.returncode == 0, (
        f"a session must not fail to start over this:\n{result.stdout}\n{result.stderr}")
    written = env_file.read_bytes()
    assert b"SOMETHING_ELSE" in written, "the wrapper took another hook's fragment out"
    assert publisher.MARKER.encode() in written, (
        "the wrapper stopped at a candidate that ran nothing, so the session was told "
        f"nothing was published:\n{written!r}\n--- stub output ---\n{result.stdout}")
    assert b"export TIMESHEET_TIMEZONE='Pacific/Auckland'\n" in written


def test_a_hook_event_given_no_env_file_is_not_a_failure(monkeypatch):
    """Not every event is handed one. A non-zero exit from a SessionStart hook is noise in
    front of a user who has done nothing wrong."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TIMESHEET_TIMEZONE", "Pacific/Auckland")
    assert publisher.main() == 0


def test_nothing_configured_still_records_that_the_hook_ran(tmp_path, monkeypatch):
    """The marker and nothing else.

    This used to write nothing at all, on the reasoning that a user who has configured
    nothing should not have an empty fragment appended every session start. That was
    right about the values and wrong about the marker: the *unconfigured* user is exactly
    who reads a missing-setting message, and withholding the marker from them makes "you
    have not configured this" indistinguishable from "your configuration did not reach
    this command" — the one distinction the marker exists to draw. Publishing it costs
    one line in a file the harness discards with the session.
    """
    env_file = tmp_path / "sessionstart-hook-0.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    for name in list(publisher.os.environ):
        if name.startswith(publisher.PREFIX):
            monkeypatch.delenv(name, raising=False)
    assert publisher.main() == 0
    assert env_file.read_bytes() == b"export BILLABLES_CONFIG_PUBLISHED='1'\n"
