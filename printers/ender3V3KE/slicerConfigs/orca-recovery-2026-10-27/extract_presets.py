"""Extract the full filament/printer/process settings embedded in Orca 3MF projects.

Writes one JSON per unique preset name into <out_dir>/<kind>/, keeping the newest project's copy.
"""
import sys, zipfile, json, os, re

list_file, out_dir = sys.argv[1], sys.argv[2]
FILAMENT_KEYS_HINT = ("filament_", "nozzle_temperature", "hot_plate_temp", "cool_plate_temp",
                      "textured_plate_temp", "eng_plate_temp", "fan_", "slow_down", "overhang_fan",
                      "close_fan", "full_fan", "reduce_fan", "additional_cooling", "temperature_vitrification",
                      "required_nozzle_HRC", "pressure_advance", "enable_pressure_advance", "chamber_temperature",
                      "activate_air_filtration", "during_print_exhaust_fan_speed", "complete_print_exhaust_fan_speed",
                      "supertack_plate_temp", "default_filament_colour", "compatible_printers")


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()


projects = []
for path in open(list_file).read().splitlines():
    try:
        cfg = json.loads(zipfile.ZipFile(path).read('Metadata/project_settings.config'))
    except Exception:
        continue
    projects.append((os.path.getmtime(path), path, cfg))
projects.sort()

written = {}
for mtime, path, cfg in projects:
    os.makedirs(os.path.join(out_dir, 'full_project_configs'), exist_ok=True)
    with open(os.path.join(out_dir, 'full_project_configs', safe(os.path.basename(path)) + '.json'), 'w') as f:
        json.dump(cfg, f, indent=2)

    for kind, key in (('filament', 'filament_settings_id'), ('machine', 'printer_settings_id'), ('process', 'print_settings_id')):
        val = cfg.get(key)
        names = val if isinstance(val, list) else [val]
        for idx, name in enumerate(names):
            if not name:
                continue
            if kind == 'filament':
                sub = {k: ([v[idx]] if isinstance(v, list) and len(v) == len(names) else v)
                       for k, v in cfg.items() if k.startswith(FILAMENT_KEYS_HINT)}
            else:
                sub = dict(cfg)
            sub['name'] = name
            sub['source_project'] = path
            os.makedirs(os.path.join(out_dir, kind), exist_ok=True)
            with open(os.path.join(out_dir, kind, safe(name) + '.json'), 'w') as f:
                json.dump(sub, f, indent=2)
            written[(kind, name)] = os.path.basename(path)

for (kind, name), src in sorted(written.items()):
    print(f"{kind:9} | {name}  <- {src}")
