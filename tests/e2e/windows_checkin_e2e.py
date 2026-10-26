"""Shared Windows end-to-end driver for the check-in watchers (check-in-answers T14, D12/D16).

Runs on `windows-latest` from `.github/workflows/checks.yml` (job `windows-e2e`). It uses the
real `aw-server` binary, runs `setup_checkin_watcher.ps1` for real (registers the logon task,
installs the pinned watcher), injects answers through the watcher's own bucket
`aw-watcher-ask-away_<host>` as real `afktask` events with `data.message`, runs the daily
scripts, and asserts what a person would see. Each step is a named function; later builds
(web watchers, retention, consent) add steps in `main()` and edit none of these.

NOT verified by this job, and never reported as passed (plan D12; Atlas decides at ship):
  - the watcher writing an event after a real away period (the answers here are injected);
  - the logon trigger firing after a real sign-in or reboot (the task is only registered
    and read back with Get-ScheduledTask);
  - a person answering the real dialog, and focus behaviour;
  - "no admin": the runner is an admin account, so that stays with the dry-run assertions
    in tests/test_checkin_watcher_setup.py.

Guided-setup steps (`step_setup_checks_pass_and_collecting`, `step_category_stage_from_a_week`)
run the install checks of `skills/setup/references/checks.md` against the real aw-server and
the category stage on a week of injected real-shape events (ACME / BETA, `example-host`).
NOT verified by those steps, and never reported as passed (Atlas decides at ship):
  - the browser-store Add click, the administrator prompt and the consent page (a person's);
  - a real person's week of titles (the week here is injected and synthetic);
  - the runner is an administrator account, so "no admin" is not shown;
  - a person's first-run experience of the menu.

Usage: python tests/e2e/windows_checkin_e2e.py <path-to-aw-server-rust.exe>
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "daily" / "scripts"
sys.path[:0] = [str(SCRIPTS), str(REPO / "skills" / "daily" / "tests")]

import support  # type: ignore[import-not-found]  # noqa: E402  # pyright: ignore[reportMissingImports]

TASK = "CheckinWatcherE2E"
PORT = 5699                      # not 5600: never the developer's own ActivityWatch
BASE = f"http://127.0.0.1:{PORT}"
HOST = "example-host"
TERMS = {"clients": [{"client": "ACME", "terms": ["acme"]}], "exclusions": []}
state: dict = {}


def check(cond, message):
    """Print each assertion, and fail the job on a false one."""
    print(("ok   " if cond else "FAIL ") + message, flush=True)
    if not cond:
        raise SystemExit(f"assertion failed: {message}")


def powershell(command):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def http(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method, headers={"Content-Type": "application/json"},
        data=None if body is None else json.dumps(body).encode("utf-8"))
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw.strip() else None


def script(name, *args):
    env = dict(os.environ, TIMESHEET_ACTIVITY_URL=BASE)
    r = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout, r.stderr


def step_install_watcher():
    """setup_checkin_watcher.ps1, for real: pinned watcher installed, ONE task registered."""
    ps1 = SCRIPTS / "setup_checkin_watcher.ps1"
    code, out = powershell(f"& '{ps1}' -TaskName {TASK} -PythonExe '{sys.executable}' -Force")
    print(out)
    check(code == 0, "setup_checkin_watcher.ps1 exits 0")
    code, out = powershell(f"(Get-ScheduledTask -TaskName {TASK}).TaskName")
    check(code == 0 and out.strip() == TASK, "Get-ScheduledTask finds the registered task")
    code, out = powershell(f"(Get-ScheduledTask -TaskName {TASK}).Principal.RunLevel")
    check(out.strip() == "Limited", "the task runs at RunLevel Limited")
    r = subprocess.run([sys.executable, "-m", "pip", "show", "aw-watcher-ask-away"],
                       capture_output=True, text=True)
    check("Version: 0.0.6" in r.stdout, "the pinned watcher 0.0.6 is installed")


def step_start_server(binary):
    """The real aw-server on a non-default port with its own data directory."""
    data = Path(tempfile.mkdtemp(prefix="billables-e2e-"))
    state["proc"] = subprocess.Popen(
        [binary, "--host", "127.0.0.1", "--port", str(PORT), "--dbpath", str(data / "e2e.db"),
         "--no-legacy-import", "--device-id", "billables-e2e"],
        stdout=open(data / "aw-server.log", "wb"), stderr=subprocess.STDOUT)
    for _ in range(200):
        try:
            http("GET", "/api/0/info")
            break
        except OSError:
            time.sleep(0.1)
    check((http("GET", "/api/0/info") or {}).get("version"), "aw-server answers on the e2e port")


def step_inject_answers():
    """Two away answers through the watcher's own bucket, shape from the real watcher."""
    d = (support.day(host=HOST).active("09:00", "12:00").afk("12:00", "12:40")
         .active("12:40", "15:00").afk("15:00", "15:40").active("15:40", "16:00")
         .afk("16:00", "16:40").active("16:40", "17:30")
         .checkin("12:00", "12:40", "call with ACME").checkin("15:00", "15:40", "lunch")
         .checkin("16:00", "16:20", "lunch").checkin("16:20", "16:40", "call with ACME"))
    state["day"] = d
    for bucket, events in d.buckets().items():
        kind = "afktask" if bucket.startswith("aw-watcher-ask-away") else (
            "afkstatus" if "afk" in bucket else "currentwindow")
        q = urllib.parse.quote(bucket, safe="")
        http("POST", f"/api/0/buckets/{q}", {"id": bucket, "client": "billables-e2e",
                                              "type": kind, "hostname": HOST})
        if events:
            http("POST", f"/api/0/buckets/{q}/events", [
                {"timestamp": e["timestamp"], "duration": e["duration"], "data": e["data"]}
                for e in events])
    events = http("GET", f"/api/0/buckets/aw-watcher-ask-away_{HOST}/events") or []
    check({e["data"]["message"] for e in events} == {"call with ACME", "lunch"},
          "both answers are in aw-watcher-ask-away_<host> with data.message")


def _day_args():
    d = state["day"]
    return d.date_str(), "--utc-offset", d.offset


def _read(tmp):
    code, out, err = script("afk_blocks.py", *_day_args(), "--json")
    check(code == 0, f"afk_blocks.py exits 0 ({err.strip()})")
    skeleton = json.loads(out)
    state["skeleton_text"] = out
    sk, terms = Path(tmp) / "skeleton.json", Path(tmp) / "terms.json"
    sk.write_text(out, encoding="utf-8")
    terms.write_text(json.dumps(TERMS), encoding="utf-8")
    code, out, err = script("checkin_answers.py", *_day_args(), "--skeleton", sk, "--terms", terms)
    check(code == 0, f"checkin_answers.py exits 0 ({err.strip()})")
    return skeleton, json.loads(out), sk, terms


def step_assert_question_not_block():
    """'call with ACME' over the break is one question quoting the answer, never a block;
    a yes on file takes it out of the questions (the ruling binds)."""
    with tempfile.TemporaryDirectory() as tmp:
        skeleton, result, sk, terms = _read(tmp)
        questions = result["questions"]
        check(len(questions) == 2, "two check-in questions: the whole break and the clipped one")
        q = questions[0]
        check(q["words"] == "call with ACME" and q["clients"] == ["ACME"],
              "the question quotes the answer and names ACME")
        check((q["start"], q["end"]) == ("12:00:00", "12:40:00"), "the question spans the break")
        check("blocks" not in result and "block" not in json.dumps(questions),
              "nothing in the result is a block")
        lunch_call = questions[1]
        check((lunch_call["start"], lunch_call["end"]) == ("16:20:00", "16:40:00"),
              "lunch then a call in one break: the question is the call only, 16:20-16:40")
        check(all(q["end"] <= "16:00:00" or q["start"] >= "16:20:00" for q in questions),
              "the lunch stretch 16:00-16:20 is in no question")
        check(all(not (b["start"] == "12:00:00" and b["end"] == "12:40:00")
                  for b in skeleton.get("blocks", [])),
              "the skeleton has no block over the answered break")
        rulings = Path(tmp) / "rulings.json"
        rulings.write_text(json.dumps({"checkin_questions": [
            {"start": q["start"], "end": q["end"], "ruling": "yes", "words": q["words"]}]}),
            encoding="utf-8")
        code, out, _ = script("checkin_answers.py", *_day_args(), "--skeleton", sk,
                              "--terms", terms, "--rulings", rulings)
        again = json.loads(out)
        check(code == 0 and [(x["start"], x["end"]) for x in again["questions"]]
              == [("16:20:00", "16:40:00")] and len(again["ruled"]) == 1,
              "a recorded yes is not asked again, and does not silence the other question")


def step_assert_lunch_stays_break():
    """'lunch' is personal: a break, no question, no hint."""
    with tempfile.TemporaryDirectory() as tmp:
        skeleton, result, _, _ = _read(tmp)
        lunch = [a for a in result["answers"] if a["words"] == "lunch"]
        check(len(lunch) == 2 and all(a["class"] == "personal" for a in lunch),
              "both lunch answers are classed personal")
        check(all(q["words"] != "lunch" for q in result["questions"] + result["hints"]),
              "lunch raises no question and no hint")
        check(all(q["words"] != "lunch" for q in result["questions"]),
              "no question carries the lunch words")
        check(any(b["start"] == "15:00:00" and b["end"] == "15:40:00"
                  for b in skeleton.get("breaks", [])), "the lunch gap is still a break")


def _post_buckets(built):
    """Create each bucket of a day on the real server and post its events."""
    for bucket, events in built.buckets().items():
        kind = ("afktask" if bucket.startswith("aw-watcher-ask-away") else
                "afkstatus" if "afk" in bucket else "currentwindow")
        q = urllib.parse.quote(bucket, safe="")
        try:
            http("POST", f"/api/0/buckets/{q}", {"id": bucket, "client": "billables-e2e",
                                                  "type": kind, "hostname": built.host})
        except urllib.error.HTTPError as exc:
            exc.close()                  # release the response body, or Python 3.14 warns
            if exc.code != 304:          # the real server's answer for a bucket that exists
                raise
        if events:
            http("POST", f"/api/0/buckets/{q}/events", [
                {"timestamp": e["timestamp"], "duration": e["duration"], "data": e["data"]}
                for e in events])


def _category_rules(workspace, *args):
    env = dict(os.environ, TIMESHEET_ACTIVITY_URL=BASE)
    r = subprocess.run([sys.executable, str(SCRIPTS / "category_rules.py"), *map(str, args),
                        "--workspace", str(workspace), "--utc-offset", "0"],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout, r.stderr


def step_setup_checks_pass_and_collecting():
    """checks.md `activity-source` against the real server, then the stated COLLECTING
    state on two recorded days (guided-setup T19, US-2/AC-2)."""
    from scenarios import real_shape_buckets, week_of_work  # type: ignore[import-not-found]
    buckets = http("GET", "/api/0/buckets/") or {}
    check(any(k.startswith("aw-watcher-window_") for k in buckets)
          and any(k.startswith("aw-watcher-afk_") for k in buckets),
          "activity-source check: /api/0/buckets/ holds aw-watcher-window_ and aw-watcher-afk_ keys")
    workspace = Path(tempfile.mkdtemp(prefix="billables-e2e-ws-"))
    state["workspace"] = workspace
    (workspace / "Timesheets").mkdir()
    (workspace / ".mcp").mkdir()
    state["week"] = week_of_work(5)
    for built in state["week"][:2]:
        _post_buckets(built)
    for name in real_shape_buckets(state["week"][0]):
        check(name in (http("GET", "/api/0/buckets/") or {}), f"the real server holds {name}")
    code, out, err = _category_rules(workspace, "--data-days")
    check(code == 0, f"category_rules.py --data-days exits 0 ({err.strip()})")
    check("COLLECTING" in out and "2 of 5" in out,
          "two recorded days end in the stated COLLECTING state (2 of 5)")
    check("say:" in out and "come back" in out, "the run prints its own say: line")
    check(not list((workspace / ".mcp").iterdir()),
          "COLLECTING wrote no rule and no backup under .mcp")


def step_category_stage_from_a_week():
    """A week of injected real-shape events, then --data-days READY, --from-context, and the
    written rules match each client's titles (US-3/AC-3)."""
    from scenarios import CONTEXT_ACME_BETA  # type: ignore[import-not-found]
    workspace = state["workspace"]
    for built in state["week"][2:]:
        _post_buckets(built)
    code, out, err = _category_rules(workspace, "--data-days")
    check(code == 0 and "READY" in out and "5 of 5" in out,
          "five recorded days read READY (5 of 5)")
    (workspace / "Timesheets" / ".context.md").write_text(CONTEXT_ACME_BETA, encoding="utf-8")
    code, out, err = _category_rules(workspace, "--inspect")
    check(code == 0 and "SAMPLE" in out, f"--inspect reads the injected titles ({err.strip()})")
    check("HOST example.invalid" in out,
          "the candidate hosts come from the injected titles (HOST example.invalid)")
    code, out, err = _category_rules(workspace, "--from-context")
    print(out)
    check(code == 0, f"--from-context exits 0 ({err.strip()})")
    verify = [line for line in out.splitlines() if line.startswith("VERIFY")]
    check(any("ACME" in line for line in verify) and any("BETA" in line for line in verify),
          "one VERIFY line each for ACME and BETA, asked of the real activity source")
    rules = (http("GET", "/api/0/settings/classes") or [])
    names = {" > ".join(r["name"]) for r in rules}
    check({"ACME", "BETA"} <= names, "the real server now holds an ACME and a BETA category")
    code, out, _ = _category_rules(workspace, "--status")
    check(out.startswith("CURRENT"), "--status reads CURRENT straight after the write")


def step_uninstall():
    """Unregister the task and compare the day's output with the watcher absent."""
    code, out = powershell(f"Unregister-ScheduledTask -TaskName {TASK} -Confirm:$false")
    check(code == 0, "Unregister-ScheduledTask succeeds")
    code, out = powershell(f"Get-ScheduledTask -TaskName {TASK} -ErrorAction SilentlyContinue")
    check(not out.strip(), "the task is gone")
    code, out2, _ = script("afk_blocks.py", *_day_args(), "--json")
    check(code == 0 and out2 == state["skeleton_text"],
          "the skeleton is byte-identical after the uninstall (the reader never wrote to it)")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "aw-watcher-ask-away"],
                   capture_output=True)


def main():
    binary = sys.argv[1]
    try:
        step_install_watcher()
        step_start_server(binary)
        step_inject_answers()
        step_assert_question_not_block()
        step_assert_lunch_stays_break()
        step_setup_checks_pass_and_collecting()
        step_category_stage_from_a_week()
        step_uninstall()
    finally:
        proc = state.get("proc")
        if proc is not None:
            proc.terminate()
    print("windows e2e: all steps passed (unverified items are listed in the module docstring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
