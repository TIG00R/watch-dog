from os import listdir
from os import stat
from os.path import isfile, join
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

TOOL_NAME = "watch_dog"

path = ""
last_mod = {}
logs = ""
_scan_num = 0

WIDTH = 76

_print_lock = threading.Lock()

_ASCII_ART_FILE = "ascii_art.txt"


def _dog_banner_lines():
    """Banner art: only from ascii_art.txt beside this script."""
    p = Path(__file__).resolve().parent / _ASCII_ART_FILE
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except OSError:
        w = 60
        return [
            "+" + "-" * w + "+",
            "|" + f" (missing {_ASCII_ART_FILE}) ".center(w) + "|",
            "+" + "-" * w + "+",
        ]


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm(p):
    try:
        return os.path.normpath(p)
    except Exception:
        return p


def _file_owner_label(path):
    try:
        st = os.stat(path)
    except OSError:
        return None

    if os.name == "posix":
        try:
            import pwd

            return pwd.getpwuid(st.st_uid).pw_name
        except (ImportError, KeyError, OverflowError):
            return f"uid:{st.st_uid}"

    if os.name == "nt":
        return _file_owner_windows(path)

    return None


def _file_owner_windows(path):
    try:
        env = os.environ.copy()
        env["WATCH_DOG_PATH"] = path
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": 15,
            "env": env,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-Command",
                "(Get-Acl -LiteralPath $env:WATCH_DOG_PATH).Owner",
            ],
            **kwargs,
        )
        if r.returncode != 0:
            return None
        out = (r.stdout or "").strip()
        return out.replace("\r\n", "\n").split("\n")[0].strip() or None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _updated_by_note(path):
    who = _file_owner_label(path)
    if not who:
        return ""
    who = who.replace("\n", " ").strip()
    if len(who) > 120:
        who = who[:117] + "..."
    return f"by {who}"


def _rule(char="="):
    return char * WIDTH


def _emit(line):
    global logs
    with _print_lock:
        if logs == "":
            print(line)
        else:
            logs.write(line + "\n")
            logs.flush()


def _emit_err(line):
    with _print_lock:
        print(line, file=sys.stderr)


def _event(is_file, action, target_path, note=""):
    verbs = {
        "added": "+ Added",
        "deleted": "- Deleted",
        "updated": "~ Updated",
    }
    verb = verbs.get(action, f"? {action}")
    label = "File" if is_file else "Directory"
    ts = _ts()
    scan = f"{_scan_num:>3}"
    p = _norm(target_path)
    base = f"[{ts} | scan {scan}]  {verb:<11}  {label:<10}  {p}"
    if note:
        base = f"{base}  |  {note}"
    if len(base) > 260:
        base = base[:257] + "..."
    _emit(base)


def _dog_banner():
    _emit(_rule("="))
    for ln in _dog_banner_lines():
        _emit(ln)
    _emit(_rule("="))


def _banner(root, interval_sec, total_scans):
    abs_root = _norm(os.path.abspath(root))
    plat = f"{sys.platform} ({os.name})"
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if logs == "":
        log_desc = "stdout (console)"
    else:
        log_desc = getattr(logs, "name", repr(logs))

    _dog_banner()
    _emit(f"  {TOOL_NAME}  - directory watcher")
    _emit(_rule("-"))
    _emit(f"  Started     : {_ts()}")
    _emit(f"  Root        : {abs_root}")
    _emit(f"  Poll every  : {interval_sec}s")
    _emit(f"  Scan cycles : {total_scans} (then exit)")
    _emit(f"  Platform    : {plat}")
    _emit(f"  Python      : {py}")
    _emit(f"  Log target  : {log_desc}")
    _emit(f"  \"By\" on ~ Updated = file owner (uid / ACL owner), not a guaranteed last editor.")
    _emit(_rule("="))


def _index_stats():
    n_dirs = len(last_mod)
    n_files = sum(len(files) for files in last_mod.values())
    return n_dirs, n_files


def _footer(root, cycles_done, interval_sec):
    abs_root = _norm(os.path.abspath(root))
    _emit("")
    _emit(_rule("="))
    _emit(f"  Session ended : {_ts()}")
    _emit(f"  Completed     : {cycles_done} scans x {interval_sec}s interval")
    _emit(f"  Watched root  : {abs_root}")
    _emit(_rule("="))


def main():
    global path, logs, _scan_num
    logs = ""
    if len(sys.argv) > 1:
        path = sys.argv[1].strip()
    else:
        try:
            path = input(f"Enter the directory path for {TOOL_NAME} to watch :  ").strip()
        except EOFError:
            print(
                f"{TOOL_NAME}: no stdin (empty input). Pass the folder to watch, e.g.\n"
                f"  python watch_dog.py C:\\\\path\\\\to\\\\folder",
                file=sys.stderr,
            )
            sys.exit(2)
    interval = 2
    total_scans = 100

    if not initialize(interval, total_scans):
        return

    for i in range(1, total_scans + 1):
        _scan_num = i
        check()
        time.sleep(interval)

    _footer(path, total_scans, interval)


def check():
    check_new_contents()
    check_deleted_contents()
    check_file_updates()


def check_new_contents():
    global last_mod
    check_new_directories(path)
    check_new_files(path)


def check_new_directories(d):
    global logs, last_mod
    for i in listdir(d):
        if join(d, i) not in last_mod.keys() and not isfile(join(d, i)):
            _event(False, "added", join(d, i))
            last_mod[join(d, i)] = {}

    for i in listdir(d):
        if join(d, i) in last_mod.keys() and not isfile(join(d, i)):
            check_new_directories(join(d, i))


def check_new_files(p):
    global logs, last_mod
    for e in listdir(p):
        if isfile(join(p, e)):
            if e not in last_mod[p]:
                st = stat(join(p, e))
                last_mod[p][e] = time.ctime(st.st_mtime)
                _event(True, "added", join(p, e))
        else:
            check_new_files(join(p, e))


def check_deleted_contents():
    check_deleted_directories()
    check_deleted_files()


def check_deleted_directories():
    global logs, last_mod
    try:
        for d in list(last_mod.keys()):
            if not os.path.exists(d):
                _event(False, "deleted", d)
                del last_mod[d]
    except Exception as ex:
        _emit_err(f"[{_ts()}] WARN  while checking deleted dirs: {ex}")


def check_deleted_files():
    global logs, last_mod
    try:
        for d in list(last_mod.keys()):
            for f in list(last_mod[d].keys()):
                if f not in listdir(d):
                    full = join(d, f)
                    del last_mod[d][f]
                    _event(True, "deleted", full)
    except Exception as ex:
        _emit_err(f"[{_ts()}] WARN  while checking deleted files: {ex}")


def check_file_updates():
    global logs, last_mod
    for d in last_mod:
        for i in list(last_mod[d].keys()):
            try:
                st = stat(join(d, i))
                new_mtime = time.ctime(st.st_mtime)
                if last_mod[d][i] != new_mtime:
                    last_mod[d][i] = new_mtime
                    full = join(d, i)
                    _event(True, "updated", full, _updated_by_note(full))
            except FileNotFoundError:
                pass


def initialize(interval_sec, total_scans):
    global path, last_mod

    if not os.path.exists(path):
        _emit_err("")
        _emit_err(_rule("!"))
        _emit_err(f"  ERROR  Path does not exist: {_norm(path)}")
        _emit_err(_rule("!"))
        _emit_err("")
        return False

    last_mod = {}
    get_files(path)
    nd, nf = _index_stats()

    _banner(path, interval_sec, total_scans)
    _emit("")
    _emit(f"  Initial index: {nd} director(y/ies), {nf} file(s) under this tree.")
    _emit(f"  Listening for changes... (Ctrl+C to stop if you run with more cycles later)")
    _emit("")
    return True


def get_files(p):
    global last_mod
    last_mod[p] = {}
    for e in listdir(p):
        if isfile(join(p, e)):
            last_mod[p][e] = time.ctime(stat(join(p, e)).st_mtime)
        else:
            get_files(join(p, e))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        print(f"{TOOL_NAME}: interrupted.", file=sys.stderr)
        sys.exit(130)
