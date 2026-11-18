from __future__ import annotations

import base64
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from .schemas import Settings
from .storage import local_path

WINDOWS_QUERY = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$os = Get-CimInstance Win32_OperatingSystem
$cpu = @(Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors)
$gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM)
[pscustomobject]@{ caption = $os.Caption; total_kib = $os.TotalVisibleMemorySize;
  free_kib = $os.FreePhysicalMemory; cpu = $cpu; gpu = $gpu } | ConvertTo-Json -Depth 4 -Compress
"""


def run(executable: str, *args: str, timeout: float = 2) -> str | None:
    try:
        result = subprocess.run([executable, *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8", errors="replace", check=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def binary(name: str, override: str = "") -> str | None:
    candidate = override or shutil.which(f"{name}.exe" if os.name == "nt" else name)
    if not candidate:
        return None
    try:
        path = local_path(candidate)
        return str(path) if path.is_file() else None
    except (OSError, ValueError, RuntimeError):
        return None


def positive(value: Any) -> int | None:
    try:
        integer = int(value)
        return integer if integer > 0 else None
    except (TypeError, ValueError):
        return None


def text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def windows_snapshot() -> dict:
    root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    powershell = root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    encoded = base64.b64encode(WINDOWS_QUERY.encode("utf-16-le")).decode("ascii")
    output = run(str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded, timeout=5)
    try:
        values = json.loads(output or "{}")
        return values if isinstance(values, dict) else {}
    except ValueError:
        return {}


def windows_ram() -> tuple[int | None, int | None]:
    try:
        import ctypes
        from ctypes import wintypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available",
                                                       "virtual_total", "virtual_available", "extended")]

        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            return memory.total, memory.available
    except (AttributeError, OSError):
        pass
    return None, None


def windows_details() -> dict:
    snapshot = windows_snapshot()
    cpus = [cpu for cpu in (snapshot.get("cpu") or []) if isinstance(cpu, dict)]
    gpus = []
    for gpu in snapshot.get("gpu") or []:
        if not isinstance(gpu, dict) or not gpu.get("Name"):
            continue
        memory = positive(gpu.get("AdapterRAM"))
        # CIM's AdapterRAM is DWORD-sized; ignore sentinel values and don't call it dedicated VRAM.
        if memory is not None and memory >= 0xFFFFFFFF:
            memory = None
        gpus.append({"name": str(gpu["Name"]), "memory_bytes": memory,
                     "memory_source": "Windows adapter report (approximate)" if memory else None})
    total_kib = positive(snapshot.get("total_kib"))
    free_kib = positive(snapshot.get("free_kib"))
    total, available = windows_ram() if not (total_kib and free_kib) else (None, None)
    names = list(dict.fromkeys(cpu["Name"].strip() for cpu in cpus if cpu.get("Name")))
    physical = [positive(cpu.get("NumberOfCores")) for cpu in cpus]
    logical = [positive(cpu.get("NumberOfLogicalProcessors")) for cpu in cpus]
    return {
        "os": snapshot.get("caption"),
        "cpu": {"name": ", ".join(names) or platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER"),
                "physical_cores": sum(physical) if physical and all(physical) else None,
                "logical_cores": sum(logical) if logical and all(logical) else os.cpu_count()},
        "memory": {"total_bytes": total_kib * 1024 if total_kib else total,
                   "available_bytes": free_kib * 1024 if free_kib else available},
        "gpus": gpus,
    }


def linux_details() -> dict:
    sections = text_file(Path("/proc/cpuinfo")).split("\n\n")
    cpus = [dict((key.strip(), value.strip()) for line in section.splitlines() if ":" in line
                 for key, value in [line.split(":", 1)]) for section in sections if section]
    physical = {(item["physical id"], item["core id"]) for item in cpus if "physical id" in item and "core id" in item}
    cpu_name = next((item.get("model name") or item.get("Hardware") for item in cpus
                     if item.get("model name") or item.get("Hardware")), None)
    mem_info = dict(re.findall(r"^(MemTotal|MemAvailable):\s+(\d+) kB", text_file(Path("/proc/meminfo")), re.M))
    total = int(mem_info["MemTotal"]) * 1024 if "MemTotal" in mem_info else None
    available = int(mem_info["MemAvailable"]) * 1024 if "MemAvailable" in mem_info else None
    limit = positive(text_file(Path("/sys/fs/cgroup/memory.max")))
    current = positive(text_file(Path("/sys/fs/cgroup/memory.current")))
    if limit and (total is None or limit < total):
        total = limit
        available = min(available, max(0, limit - current)) if available is not None and current else available
    gpu_list: list[dict] = []
    nvidia = binary("nvidia-smi")
    if nvidia:
        output = run(nvidia, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits") or ""
        for row in output.splitlines():
            if "," in row:
                name, memory = row.rsplit(",", 1)
                mib = positive(memory)
                gpu_list.append({"name": name.strip(), "memory_bytes": mib * 1024**2 if mib else None,
                                 "memory_source": "nvidia-smi" if mib else None})
    drm = Path("/sys/class/drm")
    lspci = binary("lspci")
    for card in sorted(drm.glob("card*")):
        if not re.fullmatch(r"card\d+", card.name):
            continue
        device = card / "device"
        vendor = text_file(device / "vendor")
        if vendor == "0x10de" and gpu_list and gpu_list[0].get("memory_source") == "nvidia-smi":
            continue
        if not vendor:
            continue
        model = text_file(device / "device")
        vendor_name = {"0x1002": "AMD", "0x8086": "Intel", "0x10de": "NVIDIA"}.get(vendor, f"PCI vendor {vendor}")
        description = f"{vendor_name} graphics ({model})" if model else f"{vendor_name} graphics"
        slot = device.resolve().name
        if lspci and re.fullmatch(r"[\da-f:.]+", slot, re.I):
            output = run(lspci, "-s", slot)
            if output and ": " in output:
                description = output.partition(": ")[2].strip()
        memory = positive(text_file(device / "mem_info_vram_total"))
        gpu_list.append({"name": description, "memory_bytes": memory, "memory_source": "Kernel VRAM report" if memory else None})
    return {"cpu": {"name": cpu_name or platform.processor() or None, "physical_cores": len(physical) or None,
                    "logical_cores": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()},
            "memory": {"total_bytes": total, "available_bytes": available}, "gpus": gpu_list}


def local_json(port: int, endpoint: str) -> dict:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.4)
    try:
        connection.request("GET", endpoint, headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            return {}
        data = json.loads(response.read(65536))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, http.client.HTTPException):
        return {}
    finally:
        connection.close()


def inspect_tool(name: str, override: str) -> dict:
    path = binary(name, override)
    information = run(path, "-version") if path else None
    lines = information.splitlines() if information else []
    banner = re.match(rf"^{re.escape(name)} version (\S+)", lines[0]) if lines else None
    return {"state": "ready" if banner else "error" if path or override else "missing", "path": path or override or None,
            "version": banner.group(1) if banner else None}


def media_tools(settings: Settings) -> dict:
    ffmpeg = inspect_tool("ffmpeg", settings.ffmpeg_path)
    ffprobe = inspect_tool("ffprobe", settings.ffprobe_path)
    features: dict[str, bool | None] = {"h264": None, "aac": None, "subtitles": None}
    if ffmpeg["state"] == "ready":
        encoders = run(ffmpeg["path"], "-hide_banner", "-encoders")
        filters = run(ffmpeg["path"], "-hide_banner", "-filters")
        if encoders is not None:
            features["h264"] = bool(re.search(r"^\s*V\S*\s+libx264\s", encoders, re.M))
            features["aac"] = bool(re.search(r"^\s*A\S*\s+aac\s", encoders, re.M))
        if filters is not None:
            features["subtitles"] = bool(re.search(r"^\s*[.A-Z]{3}\s+subtitles\s", filters, re.M))
    return {"ffmpeg": ffmpeg, "ffprobe": ffprobe, "features": features}


def engines() -> list[dict]:
    ollama = local_json(11434, "/api/version")
    comfy = local_json(8188, "/system_stats")
    comfy_system = comfy.get("system")
    piper = binary("piper")
    return [
        {"name": "Ollama", "state": "responding" if isinstance(ollama.get("version"), str) else "installed" if binary("ollama") else "missing",
         "version": ollama.get("version") if isinstance(ollama.get("version"), str) else None},
        {"name": "ComfyUI", "state": "responding" if isinstance(comfy_system, dict) and isinstance(comfy.get("devices"), list) else "missing",
         "version": comfy_system.get("comfyui_version") if isinstance(comfy_system, dict) and isinstance(comfy_system.get("comfyui_version"), str) else None},
        {"name": "Piper", "state": "installed" if piper else "missing", "version": None},
    ]


def disk(path: str) -> dict:
    try:
        usage = shutil.disk_usage(local_path(path))
        return {"path": path, "total_bytes": usage.total, "free_bytes": usage.free}
    except (OSError, ValueError, RuntimeError):
        return {"path": path, "total_bytes": None, "free_bytes": None}


def detect(base: Path, settings: Settings) -> dict:
    os_name = platform.system()
    spec: dict = {"cpu": {"name": platform.processor() or None, "physical_cores": None, "logical_cores": os.cpu_count()},
                  "memory": {"total_bytes": None, "available_bytes": None}, "gpus": []}
    if os_name == "Windows":
        spec.update(windows_details())
    elif os_name == "Linux":
        spec.update(linux_details())
    return {**spec, "os": spec.get("os") or f"{os_name} {platform.release()}", "architecture": platform.machine(),
            "mode": "cpu", "storage": {"workspace": disk(str(base)), "projects": disk(settings.projects_dir),
                                         "models": disk(settings.models_dir), "outputs": disk(settings.outputs_dir)},
            "media": media_tools(settings), "engines": engines(), "checked_at": datetime.now(timezone.utc).isoformat()}


class HardwareMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: tuple[float, Settings, dict] | None = None

    def read(self, base: Path, settings: Settings, *, refresh: bool = False) -> dict:
        with self._lock:
            if not refresh and self._cache:
                when, cached_settings, report = self._cache
                if cached_settings == settings and monotonic() - when < 30:
                    return report
            result = detect(base, settings)
            self._cache = (monotonic(), settings, result)
            return result
