# OrcaSlicer preset recovery (2026-10-27)

My tuned Ender-3 V3 KE presets (`@EnderKE` filaments, `Gabs EnderKE 0.4 nozzle`, the PETG/PLA processes) disappeared from OrcaSlicer a second time.
They were rebuilt from the settings that each `.3mf` project stores.

## Folders

| Folder | Content |
|---|---|
| `recovered/` | Importable Orca user presets, newest version of each. Import machine first, then filament, then process. |
| `recovered/_older_versions/` | Earlier versions of presets that changed over time. |
| `REPORT.md` | Inventory, the settings I changed vs. stock Orca, version-to-version changes, and comparison with the presets Orca had on 2026-10-27. |
| `extracted-from-3mf/` | Raw settings taken out of each project (`full_project_configs/` is the complete config per project). |
| `orca-user-folder-snapshot/` | Copy of `~/Library/Application Support/OrcaSlicer/user/` as found on 2026-10-27. |
| `vscode-history/` | `MG PLA @EnderKE` and `White PLA @EnderKE`, recovered from VS Code local history (2025-01-10). |
| `OrcaSlicer.conf` | Orca app settings as found on 2026-10-27. |
| `*.py` | Scripts that produced the above. |

## Restore

Orca: **File → Import → Import Configs…**, or copy each `recovered/<kind>/<name>.json` into
`~/Library/Application Support/OrcaSlicer/user/default/<kind>/` with an `.info` file next to it, then restart Orca.

## Rerun

```bash
find ~ -name '*.3mf' > /tmp/3mf_list.txt
python3 -I rebuild_presets.py /tmp/3mf_list.txt "$HOME/Library/Application Support/OrcaSlicer" ./out
```

## Why they vanished

Orca keeps one preset folder per login: `user/default/` when logged out, `user/<bambu-user-id>/` when logged in to Bambu.
The `@EnderKE` presets lived in the Bambu account folder and were gone from it by 2026-10-27. The exact cause is unknown.
Export a preset bundle (**File → Export → Export Preset Bundle**) after each tuning session and commit it here.
