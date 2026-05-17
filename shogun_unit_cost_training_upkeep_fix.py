#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import hashlib
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PATCH_NAME = "Shogun: Total War Gold - Unit Cost, Training, and Upkeep Fix"
VERSION = "v1.0.0"
EXE_NAME = "ShogunM.exe"
BACKUP_SUFFIX = ".unit-cost-training-upkeep-fix.bak"


@dataclass(frozen=True)
class BytePatch:
    name: str
    offset: int
    va: int
    original: bytes
    patched: bytes
    description: str


@dataclass(frozen=True)
class InspectResult:
    exe_path: Path
    sha256: str
    state_key: str
    state_label: str
    unit_fix_present: bool
    audio_fix_present: bool
    harvest_fix_present: bool
    known_hash_state: str | None
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ApplyResult:
    before: InspectResult
    after: InspectResult
    backup_path: Path | None
    created_backup: bool
    writes_applied: tuple[BytePatch, ...]


UNIT_PATCHES = (
    BytePatch(
        name="RecruitCostSizeScalar",
        offset=0x001364BC,
        va=0x005364BC,
        original=bytes.fromhex("A1 60 04 C7 00"),
        patched=bytes.fromhex("B8 3C 00 00 00"),
        description="Force the shared recruit-cost getter to use size 60.",
    ),
    BytePatch(
        name="SupportCostSumTail",
        offset=0x00135792,
        va=0x00535792,
        original=bytes.fromhex("8B C6 83 C4 04 5E 5F C3 8B F6 90 90 90 90"),
        patched=bytes.fromhex("E9 37 54 1E 00 90 90 90 90 90 90 90 90 90"),
        description="Redirect the support-cost return path to the normalizer code cave.",
    ),
    BytePatch(
        name="SupportCostCodeCave",
        offset=0x0031ABCE,
        va=0x0071ABCE,
        original=bytes(18),
        patched=bytes.fromhex("8B C6 6B C0 3C 99 F7 3D 60 04 C7 00 83 C4 04 5E 5F C3"),
        description="Normalize support totals back to 60-man economics before returning.",
    ),
    BytePatch(
        name="TrainingTimeInitLoopCompare",
        offset=0x0015C550,
        va=0x0055C550,
        original=bytes.fromhex("83 F8 64"),
        patched=bytes.fromhex("83 F8 7F"),
        description="Raise the loop-based training-time threshold above stock unit sizes.",
    ),
    BytePatch(
        name="TrainingTimeInitLoopSpecialCompare",
        offset=0x0015C57E,
        va=0x0055C57E,
        original=bytes.fromhex("83 F8 64"),
        patched=bytes.fromhex("83 F8 7F"),
        description="Keep the special 4-season entry from becoming 8 seasons at size 120.",
    ),
    BytePatch(
        name="TrainingTimeInitUnrolledCompare",
        offset=0x0017CAEE,
        va=0x0057CAEE,
        original=bytes.fromhex("83 F8 64"),
        patched=bytes.fromhex("83 F8 7F"),
        description="Raise the unrolled training-time threshold above stock unit sizes.",
    ),
    BytePatch(
        name="TrainingTimeDoublePassACompare",
        offset=0x001BFA08,
        va=0x005BFA08,
        original=bytes.fromhex("83 FA 64"),
        patched=bytes.fromhex("83 FA 7F"),
        description="Prevent the first late training-time doubling pass from firing at size 120.",
    ),
    BytePatch(
        name="TrainingTimeDoublePassBCompare",
        offset=0x002E3213,
        va=0x006E3213,
        original=bytes.fromhex("83 F8 64"),
        patched=bytes.fromhex("83 F8 7F"),
        description="Prevent the second late training-time doubling pass from firing at size 120.",
    ),
)

AUDIO_FIX_PATCHES = (
    BytePatch(
        name="AudioEosCheckEntry",
        offset=0x001B7CCB,
        va=0x005B7CCB,
        original=bytes.fromhex("8B 4E 60 85 C9 74"),
        patched=bytes.fromhex("E9 10 2F 16 00 90"),
        description="Audio fix EOF-check redirect.",
    ),
    BytePatch(
        name="AudioDurationScalingGate",
        offset=0x001B80D2,
        va=0x005B80D2,
        original=bytes.fromhex("8A 45 18 84 C0 75 32"),
        patched=bytes.fromhex("E9 49 2B 16 00 90 90"),
        description="Audio fix duration-scaling redirect.",
    ),
    BytePatch(
        name="AudioPostEofDelayGate",
        offset=0x001B7916,
        va=0x005B7916,
        original=bytes.fromhex("8A 45 18 84 C0 74 07 B8 01 00 00 00 EB 05"),
        patched=bytes.fromhex("E9 1C 33 16 00 90 90 90 90 90 90 90 90 90"),
        description="Audio fix post-EOF delay redirect.",
    ),
    BytePatch(
        name="AudioStreamTimingCodeCave",
        offset=0x0031ABE0,
        va=0x0071ABE0,
        original=bytes(0x78),
        patched=bytes.fromhex(
            "8B 4E 60 85 C9 75 34 8B 4E 54 85 C9 74 23 8D 44 "
            "24 10 50 51 8B 01 FF 50 20 85 C0 7C 14 8B 54 24 "
            "10 8B 7C 24 14 8B 46 40 8B 76 44 29 C2 19 F7 7C "
            "05 E9 E4 D0 E9 FF E9 EA D0 E9 FF E9 B2 D0 E9 FF "
            "83 7D 60 00 74 0C 8A 45 18 84 C0 75 05 E9 A7 D4 "
            "E9 FF E9 D4 D4 E9 FF 83 7D 60 00 74 07 8A 45 18 "
            "84 C0 74 0A B8 01 00 00 00 E9 DB CC E9 FF B8 88 "
            "13 00 00 E9 D1 CC E9 FF"
        ),
        description="Audio fix stream-timing code cave.",
    ),
    BytePatch(
        name="AudioScriptCleanupGate",
        offset=0x00198FA5,
        va=0x00598FA5,
        original=bytes.fromhex("A9 FF 00 00 00 75 05 E8 2F F8 FF FF"),
        patched=bytes.fromhex("E9 AE 1C 18 00 90 90 90 90 90 90 90"),
        description="Audio fix script-cleanup redirect.",
    ),
    BytePatch(
        name="AudioCleanupGuardCodeCave",
        offset=0x0031AC58,
        va=0x0071AC58,
        original=bytes(0x20),
        patched=bytes.fromhex(
            "A9 FF 00 00 00 75 14 8B 0D 80 79 C9 00 85 C9 74 "
            "05 80 39 00 75 05 E8 6D DB E7 FF E9 39 E3 E7 FF"
        ),
        description="Audio fix cleanup-guard code cave.",
    ),
)

HARVEST_WAV_SUFFIX_BYTES = bytes.fromhex("60 32 F1 00")
HARVEST_MP3_SUFFIX_BYTES = bytes.fromhex("80 33 F1 00")

HARVEST_FRAME_ID_SETUP = bytes.fromhex(
    "33 C9 "
    "89 8C 24 80 02 00 00 "
    "89 8C 24 84 02 00 00 "
    "C7 84 24 88 02 00 00 0E 00 00 00 "
    "B8 0D 00 00 00 "
    "89 84 24 8C 02 00 00 "
    "89 84 24 90 02 00 00"
)

HARVEST_AUDIO_CAVE_TAIL = bytes.fromhex(
    "9C 60 8B 0D 1C 88 C2 00 85 "
    "C9 74 11 6A 01 E8 E6 D2 E2 FF C7 05 1C 88 C2 00 "
    "00 00 00 00 6A 68 E8 C4 15 FE FF 83 C4 04 85 C0 "
    "74 26 89 C6 31 D2 88 56 01 89 56 04 89 56 08 C6 "
    "46 0C 01 8D 94 24 64 02 00 00 52 89 F1 E8 AE D5 "
    "E9 FF 89 35 1C 88 C2 00 61 9D 31 C9 E9 A5 F0 E2 FF"
)

RESTORED_HARVEST_CODE_CAVE = HARVEST_FRAME_ID_SETUP + (b"\x90" * 9) + HARVEST_AUDIO_CAVE_TAIL

HARVEST_PATCHES = (
    BytePatch(
        name="HarvestReportUseMp3Suffix",
        offset=0x00149D7F,
        va=0x00549D7F,
        original=HARVEST_WAV_SUFFIX_BYTES,
        patched=HARVEST_MP3_SUFFIX_BYTES,
        description="Use Gold's MP3 harvest voice clips, including Japanese Foices assets.",
    ),
    BytePatch(
        name="HarvestReportVoiceHook",
        offset=0x00149D88,
        va=0x00549D88,
        original=HARVEST_FRAME_ID_SETUP,
        patched=bytes.fromhex(
            "E9 F3 0E 1D 00 "
            "90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 "
            "90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 "
            "90 90 90 90 90 90 90 90 90"
        ),
        description="Redirect harvest report setup to the restoration code cave.",
    ),
    BytePatch(
        name="HarvestReportCodeCave",
        offset=0x0031AC80,
        va=0x0071AC80,
        original=bytes(0x91),
        patched=RESTORED_HARVEST_CODE_CAVE,
        description="Start harvest audio while preserving Epic.BIF harvest illustration frame IDs.",
    ),
)

KNOWN_STATE_HASHES = {
    "original": "4445DCB123D595A9B68FD18A20B98A9F9332F9651474976636CB9EC54F3D16AF",
    "unit_fix_only": "A6CECD32946C10B152ADBC8D922BEAC8A67F7A639E6C4A10297297310C427285",
    "audio_fix_only": "11356636154934CC2FF2ED26B46FD82155C05EB52873FE6763F7FD22B1344D32",
    "unit_audio_fixes": "141C971763DC50AC2D5DD131E7FECAE87914C96FDB87B4EF25820E3B7A8C89DC",
    "audio_harvest_fixes": "C7C3A70B5F281546F6A44F975EE795EE157D72A276007F983588F55EC88A9B89",
    "unit_audio_harvest_fixes": "1154B5703769809D56B80DDB5B25BD98DEE2DED19721AEEFA9254D3EB81A9F78",
}

STATE_LABELS = {
    "original": "Original executable",
    "unit_fix_only": "Unit cost + upkeep + training-time fix applied",
    "audio_fix_only": "Audio fix applied",
    "unit_audio_fixes": "Unit cost + upkeep + training-time fix + audio fix applied",
    "audio_harvest_fixes": "Audio fix + harvest report restoration fix applied",
    "unit_audio_harvest_fixes": "Unit cost + upkeep + training-time fix + audio fix + harvest report restoration fix applied",
    "unknown_unsupported": "Unknown or unsupported executable state",
}

PATCHABLE_STATES = {"original", "audio_fix_only", "audio_harvest_fixes"}

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_BEGIN = 0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def resolve_exe(target: str | Path) -> Path:
    path = Path(target).expanduser().resolve()
    if path.is_dir():
        path = path / EXE_NAME
    if not path.exists():
        raise FileNotFoundError(f"target not found: {path}")
    if path.name.lower() != EXE_NAME.lower():
        raise ValueError(f"target must be {EXE_NAME} or its game folder: {path}")
    return path


def backup_path(exe_path: Path) -> Path:
    return exe_path.with_name(exe_path.name + BACKUP_SUFFIX)


def find_known_hash_state(sha256_hex: str) -> str | None:
    for state_key, known_hash in KNOWN_STATE_HASHES.items():
        if sha256_hex == known_hash:
            return state_key
    return None


def patch_group_status(data: bytes, patches: tuple[BytePatch, ...]) -> tuple[str, tuple[str, ...]]:
    slot_states = []
    notes = []
    for patch in patches:
        current = data[patch.offset : patch.offset + len(patch.original)]
        if current == patch.original:
            slot_states.append("original")
        elif current == patch.patched:
            slot_states.append("patched")
        else:
            slot_states.append("unknown")
            notes.append(
                f"{patch.name}: unsupported bytes at 0x{patch.offset:08X} "
                f"(found {current.hex(' ')})"
            )

    unique = set(slot_states)
    if "unknown" in unique:
        return "unknown", tuple(notes)
    if unique == {"original"}:
        return "clean", ()
    if unique == {"patched"}:
        return "patched", ()
    return "mixed", ("Partially applied patch group detected.",)


def inspect_exe(exe_path: Path) -> InspectResult:
    data = exe_path.read_bytes()
    digest = sha256_bytes(data)
    unit_group, unit_notes = patch_group_status(data, UNIT_PATCHES)
    audio_group, audio_notes = patch_group_status(data, AUDIO_FIX_PATCHES)
    harvest_group, harvest_notes = patch_group_status(data, HARVEST_PATCHES)
    notes = list(unit_notes + audio_notes + harvest_notes)

    if "unknown" in (unit_group, audio_group, harvest_group) or "mixed" in (unit_group, audio_group, harvest_group):
        state_key = "unknown_unsupported"
    elif harvest_group == "patched" and audio_group != "patched":
        notes.append("Harvest restoration bytes are present without the required audio fix bytes.")
        state_key = "unknown_unsupported"
    elif unit_group == "clean" and audio_group == "clean" and harvest_group == "clean":
        state_key = "original"
    elif unit_group == "patched" and audio_group == "clean" and harvest_group == "clean":
        state_key = "unit_fix_only"
    elif unit_group == "clean" and audio_group == "patched" and harvest_group == "clean":
        state_key = "audio_fix_only"
    elif unit_group == "patched" and audio_group == "patched" and harvest_group == "clean":
        state_key = "unit_audio_fixes"
    elif unit_group == "clean" and audio_group == "patched" and harvest_group == "patched":
        state_key = "audio_harvest_fixes"
    elif unit_group == "patched" and audio_group == "patched" and harvest_group == "patched":
        state_key = "unit_audio_harvest_fixes"
    else:
        state_key = "unknown_unsupported"

    known_hash_state = find_known_hash_state(digest)
    if state_key != "unknown_unsupported":
        expected_hash = KNOWN_STATE_HASHES[state_key]
        if digest != expected_hash:
            notes.append(
                "Patch bytes match a supported state, but the SHA-256 does not match the reference executable."
            )
        if known_hash_state and known_hash_state != state_key:
            notes.append(
                f"SHA-256 matches '{known_hash_state}', but patch bytes match '{state_key}'."
            )
            state_key = "unknown_unsupported"

    return InspectResult(
        exe_path=exe_path,
        sha256=digest,
        state_key=state_key,
        state_label=STATE_LABELS[state_key],
        unit_fix_present=unit_group == "patched",
        audio_fix_present=audio_group == "patched",
        harvest_fix_present=harvest_group == "patched",
        known_hash_state=known_hash_state,
        notes=tuple(notes),
    )


def create_file_shared(path: Path, access: int):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p

    last_error = 0
    for _ in range(80):
        handle = kernel32.CreateFileW(
            str(path),
            access,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle != INVALID_HANDLE_VALUE:
            return kernel32, handle
        last_error = ctypes.get_last_error()
        if last_error != 32:
            raise ctypes.WinError(last_error)
        time.sleep(0.25)
    raise ctypes.WinError(last_error)


def write_shared(path: Path, writes: list[tuple[int, bytes]]) -> None:
    kernel32, handle = create_file_shared(path, GENERIC_READ | GENERIC_WRITE)
    kernel32.SetFilePointerEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        ctypes.c_uint32,
    ]
    kernel32.SetFilePointerEx.restype = ctypes.c_int
    kernel32.WriteFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = ctypes.c_int
    kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    kernel32.FlushFileBuffers.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    try:
        new_pos = ctypes.c_longlong()
        for offset, payload in writes:
            if not kernel32.SetFilePointerEx(handle, offset, ctypes.byref(new_pos), FILE_BEGIN):
                raise ctypes.WinError(ctypes.get_last_error())
            written = ctypes.c_uint32()
            buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
            if not kernel32.WriteFile(
                handle,
                ctypes.cast(buffer, ctypes.c_void_p),
                len(payload),
                ctypes.byref(written),
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value != len(payload):
                raise RuntimeError(
                    f"short write at 0x{offset:08X}: wrote {written.value} of {len(payload)} bytes"
                )
        if not kernel32.FlushFileBuffers(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def chunk_writes(blob: bytes, chunk_size: int = 1 << 20) -> list[tuple[int, bytes]]:
    return [(offset, blob[offset : offset + chunk_size]) for offset in range(0, len(blob), chunk_size)]


def restore_blob(exe_path: Path, blob: bytes) -> None:
    if exe_path.exists() and exe_path.stat().st_size == len(blob):
        write_shared(exe_path, chunk_writes(blob))
    else:
        temp_path = exe_path.with_name(exe_path.name + ".tmp")
        temp_path.write_bytes(blob)
        shutil.move(str(temp_path), str(exe_path))


def apply_unit_fix(exe_path: Path) -> ApplyResult:
    before = inspect_exe(exe_path)
    if before.state_key == "unknown_unsupported":
        raise RuntimeError("The target executable is in an unknown or unsupported state.")
    if before.state_key in {"unit_fix_only", "unit_audio_fixes", "unit_audio_harvest_fixes"}:
        return ApplyResult(before=before, after=before, backup_path=backup_path(exe_path), created_backup=False, writes_applied=())
    if before.state_key not in PATCHABLE_STATES:
        raise RuntimeError(f"This patcher cannot patch state '{before.state_key}'.")

    backup = backup_path(exe_path)
    created_backup = False
    if not backup.exists():
        shutil.copy2(exe_path, backup)
        created_backup = True

    data = exe_path.read_bytes()
    writes = []
    applied = []
    for patch in UNIT_PATCHES:
        current = data[patch.offset : patch.offset + len(patch.original)]
        if current == patch.patched:
            continue
        if current != patch.original:
            raise RuntimeError(
                f"Unsupported bytes at 0x{patch.offset:08X} for {patch.name}: {current.hex(' ')}"
            )
        writes.append((patch.offset, patch.patched))
        applied.append(patch)

    if writes:
        write_shared(exe_path, writes)

    after = inspect_exe(exe_path)
    expected_states = {
        "original": "unit_fix_only",
        "audio_fix_only": "unit_audio_fixes",
        "audio_harvest_fixes": "unit_audio_harvest_fixes",
    }
    expected_state = expected_states[before.state_key]
    if after.state_key != expected_state:
        raise RuntimeError(
            f"Patch completed, but the resulting state is '{after.state_key}' instead of '{expected_state}'."
        )

    return ApplyResult(
        before=before,
        after=after,
        backup_path=backup,
        created_backup=created_backup,
        writes_applied=tuple(applied),
    )


def restore_unit_fix(exe_path: Path) -> InspectResult:
    backup = backup_path(exe_path)
    if not backup.exists():
        raise FileNotFoundError(f"backup not found: {backup}")
    restore_blob(exe_path, backup.read_bytes())
    return inspect_exe(exe_path)


def print_header() -> None:
    print(f"{PATCH_NAME} {VERSION}")
    print("=" * (len(PATCH_NAME) + len(VERSION) + 1))


def print_inspection(result: InspectResult) -> None:
    print(f"target={result.exe_path}")
    print(f"sha256={result.sha256}")
    print(f"state={result.state_key}")
    print(f"state_label={result.state_label}")
    print(f"unit_fix_present={'yes' if result.unit_fix_present else 'no'}")
    print(f"audio_fix_present={'yes' if result.audio_fix_present else 'no'}")
    print(f"harvest_restoration_fix_present={'yes' if result.harvest_fix_present else 'no'}")
    print(f"known_reference_hash={result.known_hash_state if result.known_hash_state else 'no'}")
    print(f"backup={backup_path(result.exe_path) if backup_path(result.exe_path).exists() else 'not_found'}")
    for note in result.notes:
        print(f"note={note}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply, verify, or restore the SHOGUN: Total War Gold unit cost + upkeep + training-time fix."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Path to ShogunM.exe or the game folder containing it. Defaults to the current directory.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only inspect the executable and print its detected state.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help=f"Restore the executable from {BACKUP_SUFFIX}.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.verify and args.restore:
        parser.error("--verify and --restore cannot be used together")

    print_header()

    try:
        exe_path = resolve_exe(args.target)

        if args.verify:
            result = inspect_exe(exe_path)
            print_inspection(result)
            return 0 if result.state_key != "unknown_unsupported" else 1

        if args.restore:
            result = restore_unit_fix(exe_path)
            print(f"restored_from={backup_path(exe_path)}")
            print_inspection(result)
            return 0 if result.state_key != "unknown_unsupported" else 1

        applied = apply_unit_fix(exe_path)
        if applied.writes_applied:
            if applied.created_backup:
                print(f"backup_created={applied.backup_path}")
            else:
                print(f"backup_preserved={applied.backup_path}")
            for patch in applied.writes_applied:
                print(
                    f"patched {patch.name} file=0x{patch.offset:08X} "
                    f"va=0x{patch.va:08X} description={patch.description}"
                )
        else:
            print("status=already_patched_for_this_fix")
            if applied.backup_path and applied.backup_path.exists():
                print(f"backup_preserved={applied.backup_path}")
        print_inspection(applied.after)
        return 0 if applied.after.state_key != "unknown_unsupported" else 1
    except Exception as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
