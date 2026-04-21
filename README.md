# Shogun: Total War Gold — Unit Cost, Training, and Upkeep Fix

Patches `ShogunM.exe` on the GOG and Steam builds of **SHOGUN: Total War** so that recruit cost, upkeep, and training time stay at their original 60-man campaign values when battle unit size is set to 120.

Compatible with the separate [throne-room audio fix](https://github.com/LouieWoolger/shogun-total-war-throne-room-audio-fix/tree/main). The two patches touch different file offsets and can be applied in either order.

## The problem

Shogun: Total War lets you raise the default battle unit size from 60 to 120 men. This is a battlefield preference — more troops per unit makes engagements feel larger and more cinematic. Changing it should not alter the campaign economy.

Without this fix, setting unit size to 120 also changes three campaign values:

- **Recruit cost** doubles. The game computes recruit cost against current unit size rather than a fixed baseline, so a 2× size increase produces a 2× price increase.
- **Upkeep scales proportionally.** The support-cost calculation uses the same unit-size multiplier, so maintaining any given army costs roughly twice as much per turn at size 120.
- **Training time increases.** The executable contains hardcoded threshold checks: if unit size ≥ 100, extended training times apply. At size 120 that threshold fires, lengthening or doubling recruitment turns across the unit roster. A unit that normally takes 1 season to train can take 2.

The entire campaign economy was designed and balanced around 60-man units. Province income, building costs, and diplomatic penalties were never adjusted to match the larger unit size. The result is a campaign that is more expensive and slower to build armies in, with none of the surrounding systems rebalanced to compensate.

## What this fix changes

Eight byte patches to `ShogunM.exe`:

| Patch | What it does |
|---|---|
| `RecruitCostSizeScalar` | Forces the recruit-cost getter to use a constant size of 60 instead of reading the current unit size from memory. |
| `SupportCostSumTail` | Redirects the support-cost return path to a normaliser code cave. |
| `SupportCostCodeCave` | Multiplies the computed support total by 60 and divides by the current unit size before returning, restoring 60-man economics regardless of the active unit size setting. |
| `TrainingTimeInitLoopCompare` | Raises the loop-path training-time threshold from 100 to 127, keeping size 120 below it. |
| `TrainingTimeInitLoopSpecialCompare` | Raises the same threshold on the special path that would otherwise double a 1-season training time to 2 seasons at size 120. |
| `TrainingTimeInitUnrolledCompare` | Raises the equivalent threshold on the unrolled code path. |
| `TrainingTimeDoublePassACompare` | Prevents the first late training-time doubling pass from firing at size 120. |
| `TrainingTimeDoublePassBCompare` | Prevents the second late training-time doubling pass from firing at size 120. |

All patches target specific file offsets. The patcher reads and validates the exact bytes at every location before writing anything.

## What this fix does not change

- Battle unit size. Units on the field remain at whatever size you have set.
- Unit combat stats, movement, or any other battle-side values.
- Campaign data files. Only `ShogunM.exe` is touched.
- The separate throne-room audio fix. If it is already applied, this patcher detects it and leaves those bytes intact.
- Any executable other than the specific GOG/Steam `ShogunM.exe` states listed under [Supported targets](#supported-targets).

## Requirements

- Windows
- Python 3.9 or newer

## Usage

**Patch** (pass the game folder or the executable directly):

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold"
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold\ShogunM.exe"
```

With no argument, the script looks for `ShogunM.exe` in the current directory:

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py
```

**Inspect only (no changes written):**

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold" --verify
```

**Restore from backup:**

```powershell
python .\shogun_unit_cost_training_upkeep_fix.py "C:\GOG Games\SHOGUN Total War Gold" --restore
```

`--verify` and `--restore` cannot be combined.

## Backup and restore

Before writing any changes, the patcher creates:

````
ShogunM.exe.unit-cost-training-upkeep-fix.bak
````

in the same folder as the executable — but only if that file does not already exist. If you run the patcher a second time, your original backup is preserved.

This name is intentionally distinct from the backup created by the audio-fix patcher, which uses:

````
ShogunM.exe.bak
````

If the audio fix is already applied when you run this patcher, the backup contains the audio-fixed executable. Restoring later returns you to that audio-fixed state, not to the bare original.

## Compatibility with the audio fix

Verified against: [LouieWoolger/shogun-total-war-throne-room-audio-fix](https://github.com/LouieWoolger/shogun-total-war-throne-room-audio-fix/tree/main)

The two patch sets write to different file offsets with no overlap and can be applied in either order. This patcher explicitly detects whether the audio fix is present and preserves it in all code paths.

## Supported targets

The patcher recognises five states and will only write to the two marked as patchable:

| State key | Description | Patchable |
|---|---|---|
| `original` | Unmodified executable | ✓ |
| `audio_fix_only` | Audio fix applied, this fix not yet applied | ✓ |
| `unit_fix_only` | This fix applied, audio fix not present | — already done |
| `both_fixes` | Both fixes applied | — already done |
| `unknown_unsupported` | Bytes at any patch location are not recognised | ✗ |

Known SHA-256 values for the reference executable (GOG and Steam ship the same `ShogunM.exe`):

````
4445DCB123D595A9B68FD18A20B98A9F9332F9651474976636CB9EC54F3D16AF  original
A6CECD32946C10B152ADBC8D922BEAC8A67F7A639E6C4A10297297310C427285  unit_fix_only
11356636154934CC2FF2ED26B46FD82155C05EB52873FE6763F7FD22B1344D32  audio_fix_only
141C971763DC50AC2D5DD131E7FECAE87914C96FDB87B4EF25820E3B7A8C89DC  both_fixes
````

If your executable is at a different hash, run `--verify` first. If it reports `unknown_unsupported`, restore a clean `ShogunM.exe` before patching.

## Verifying the fix in-game

1. Launch the patched game and set battle unit size to 120.
2. Start a new campaign or load an existing one.
3. Open the recruitment panel. Units that cost, for example, 100 koku at 60-man size should still show 100 koku — not 200.
4. Check training time. A unit that normally recruits in 1 or 2 turns should still take 1 or 2 turns, not more.
5. Check your upkeep total after recruiting several units. It should match what you would expect at 60-man pricing.

If the audio fix is also applied, throne-room speech should play normally and be unaffected by this patch.

## Technical details

Campaign values are hardcoded in unit templates inside `ShogunM.exe`, not in any editable data file. The relevant template fields are:

````
template + 0x58  recruitment/training time
template + 0x5C  recruit cost
template + 0x60  support/upkeep coefficient
````

**Recruit cost** is computed by a getter that loads current unit size from `[0x00C70460]` and scales cost against it. The fix replaces that load with a constant move of 60 (`MOV EAX, 0x3C`), so the getter always produces 60-man values.

**Support cost** is accumulated across units and returned through a shared tail. The fix redirects that return path to a code cave that normalises the accumulated total: multiply by 60, divide by the value at `[0x00C70460]` (current unit size). The result is the correct 60-man support figure regardless of the size setting.

**Training time** is gated by five `cmp eax, 0x64` checks (compare unit size to 100). At size 120, all five fire and cause extended or doubled training durations. The fix changes each comparison to `cmp eax, 0x7F` (compare to 127). Size 120 falls below that threshold; size 60 was already below the original 100 and is unaffected either way.

## Notes

- `status=already_patched_for_this_fix` — the unit-fix bytes were already present; nothing was written.
- `audio_fix_present=yes` — the audio fix was detected and left intact.
- `unknown_unsupported` — one or more byte locations contain unexpected values. Restore a clean `ShogunM.exe` first.
- `backup_created=` — path to the newly created backup.
- `backup_preserved=` — an existing backup was found and left untouched.
