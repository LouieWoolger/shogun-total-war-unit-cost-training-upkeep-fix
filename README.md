> [!IMPORTANT]
> Superseded by the **[Unofficial Shogun: Total War Collection Patch](https://github.com/LouieWoolger/shogun-total-war-collection-unofficial-patch)** — a combined GUI installer containing all fixes.

# Shogun: Total War Gold — Unit Cost, Training, and Upkeep Fix
[![Discord](https://img.shields.io/discord/1505490825889579018?style=for-the-badge&logo=discord&label=Discord&color=5865F2)](https://discord.gg/zKbDADqWRC)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5F5F?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/louiewoolger)

Patches `ShogunM.exe` on Shogun: Total War Gold (GOG/Steam) so that recruit cost, upkeep, and training time stay at their 60-man campaign values when battle unit size is set to 120. Without this fix, raising unit size to 120 doubles recruit costs, scales upkeep proportionally, and triggers hardcoded training-time thresholds that were never intended to fire at size 120.

Compatible with the [throne-room audio fix](https://github.com/LouieWoolger/shogun-total-war-throne-room-audio-fix) and the [harvest report restoration fix](https://github.com/LouieWoolger/shogun-total-war-harvest-report-voice-fix). The unit-cost, throne-room audio, and harvest report patch sets touch different file offsets and can be applied in any order. The harvest report restoration fix includes the throne-room audio fix.

## Requirements

- Windows
- Python 3.9 or newer

## Usage

Pass the game folder or the path to `ShogunM.exe`:

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold"
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold\ShogunM.exe"
```

With no argument, the script looks for `ShogunM.exe` in the current directory.

Inspect without writing changes:

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold" --verify
```

Restore from backup:

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold" --restore
```

`--verify` and `--restore` cannot be combined.

## Notes

Before patching, the script creates `ShogunM.exe.unit-cost-training-upkeep-fix.bak` in the same folder as the EXE. An existing backup is preserved. This name is distinct from the audio fix's backup (`ShogunM.exe.throne-room-audio-fix.bak`) and the harvest fix's backup (`ShogunM.exe.harvest-report-restoration-fix.bak`), so all three can coexist.

The patcher will only write the unit-cost bytes and will preserve any audio or harvest report fix bytes already present. If `--verify` reports `unknown_unsupported`, restore a clean `ShogunM.exe` first.

Known SHA-256 values:

```
4445DCB123D595A9B68FD18A20B98A9F9332F9651474976636CB9EC54F3D16AF  original
A6CECD32946C10B152ADBC8D922BEAC8A67F7A639E6C4A10297297310C427285  unit fix only
11356636154934CC2FF2ED26B46FD82155C05EB52873FE6763F7FD22B1344D32  audio fix only
141C971763DC50AC2D5DD131E7FECAE87914C96FDB87B4EF25820E3B7A8C89DC  unit + audio fixes
C7C3A70B5F281546F6A44F975EE795EE157D72A276007F983588F55EC88A9B89  audio + harvest report fixes
1154B5703769809D56B80DDB5B25BD98DEE2DED19721AEEFA9254D3EB81A9F78  unit + audio + harvest report fixes
```

Status messages:

- `status=already_patched_for_this_fix` — patch is present; no changes were made
- `audio_fix_present=yes` — audio fix bytes were detected and left intact
- `harvest_restoration_fix_present=yes` — harvest report restoration bytes were detected and left intact
- `unknown_unsupported` — unexpected bytes at one or more patch locations
