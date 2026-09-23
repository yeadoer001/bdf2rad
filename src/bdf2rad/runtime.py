"""Read-only discovery; subprocesses are always run in an explicit output directory."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

OFFICIAL_URLS = (
    "https://github.com/OpenRadioss/OpenRadioss",
    "https://github.com/OpenRadioss/Tools",
    "https://openradioss.atlassian.net/wiki/spaces/OPENRADIOSS",
    "https://help.altair.com/hwdesktop/hwx/topics/conversion_between_solvers/convert_nastran_to_radioss_mapping.htm",
)


def probe_command(argv, cwd, env=None):
    try:
        p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                           errors="replace", timeout=20)
        return {"command": argv, "returncode": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": argv, "error": str(exc)}


def solver_environment(root: Path):
    env = os.environ.copy()
    env.update(OPENRADIOSS_PATH=str(root), RAD_CFG_PATH=str(root / "hm_cfg_files"),
               RAD_H3D_PATH=str(root / "extlib/h3d/lib/win64"), OMP_NUM_THREADS="1")
    dll_dirs = [root / "extlib/hm_reader/win64", root / "extlib/intelOneAPI_runtime/win64"]
    env["PATH"] = os.pathsep.join([*(str(p) for p in dll_dirs), env.get("PATH", "")])
    return env


def check_url(url):
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            data = response.read(4 * 1024 * 1024)
            return {"url": url, "status": response.status, "resolved_url": response.url,
                    "bytes_read": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "note": "HTTP accessibility only; not keyword validation"}
    except Exception as exc:
        return {"url": url, "error": str(exc)}


def discover(search_roots, output: Path, online=False, solver_help=False):
    output.mkdir(parents=True, exist_ok=True)
    roots = [Path(p).resolve() for p in search_roots]
    for key in ("OPENRADIOSS_PATH", "RAD_CFG_PATH"):
        if os.environ.get(key):
            p = Path(os.environ[key]).resolve()
            roots.append(p.parent if key == "RAD_CFG_PATH" else p)
    # PATH can locate installed executables even without a supplied root.
    for exe in ("starter_win64.exe", "starter_linux64_gf", "engine_win64.exe"):
        found = shutil.which(exe)
        if found:
            roots.append(Path(found).parent.parent)
    roots = list(dict.fromkeys(roots))
    report = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "python": sys.executable,
              "workspace": str(Path.cwd()), "search_roots": list(map(str, roots)),
              "scope": "Only supplied roots, environment roots and PATH; not an all-drive scan",
              "commands": [], "executables": [], "config_directories": [],
              "source_archives": [], "source_directories": [], "scan_errors": [],
              "optional_modules": {m: importlib.util.find_spec(m) is not None
                                   for m in ("numpy", "pytest", "yaml", "pyNastran")}}
    for name in ("python", "py", "git"):
        exe = shutil.which(name)
        report["commands"].append(probe_command([exe, "--version"], output) if exe
                                   else {"command": [name], "error": "Not on PATH"})
    seen = set()
    for root in roots:
        if not root.is_dir():
            report["scan_errors"].append(f"Not a directory: {root}")
            continue
        for directory, dirs, files in os.walk(root, onerror=lambda e: report["scan_errors"].append(str(e))):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv")]
            path = Path(directory)
            if path in seen:
                dirs[:] = []
                continue
            seen.add(path)
            if path.name == "hm_cfg_files":
                report["config_directories"].append({"path": str(path),
                    "radioss_versions": sorted(p.name for p in (path / "config/CFG").glob("radioss*"))})
                dirs[:] = []
            if (path / "starter/source").is_dir() and (path / "engine/source").is_dir():
                report["source_directories"].append(str(path))
            for name in files:
                p = path / name
                if name.lower().startswith(("starter_", "engine_")) and (p.suffix == ".exe" or not p.suffix):
                    item = {"path": str(p), "size": p.stat().st_size}
                    if solver_help and "_sp" not in name and "_impi" not in name:
                        item["help"] = probe_command([str(p), "-help"], output, solver_environment(p.parent.parent))
                    report["executables"].append(item)
                if name.lower().startswith("openradioss") and p.suffix.lower() == ".zip":
                    try:
                        with zipfile.ZipFile(p) as archive:
                            entries = archive.namelist()
                            source = [n for n in entries if "/starter/source/" in n and not n.endswith("/")]
                            if source:
                                report["source_archives"].append({"path": str(p), "entries": len(entries),
                                    "starter_source_files": len(source),
                                    "examples": sum(n.endswith(".rad") for n in entries)})
                    except (OSError, zipfile.BadZipFile) as exc:
                        report["scan_errors"].append(str(exc))
    if online:
        with ThreadPoolExecutor(max_workers=4) as pool:
            report["official_access"] = list(pool.map(check_url, OFFICIAL_URLS))
    else:
        report["official_access"] = [{"url": u, "status": "NOT_CHECKED"} for u in OFFICIAL_URLS]
    report["solver_validation"] = "NOT_RUN (help output is not Starter/Engine model validation)"
    return report
