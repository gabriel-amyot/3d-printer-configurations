import sys, zipfile, json

for path in open(sys.argv[1]).read().splitlines():
    name = path.split('/')[-1]
    try:
        cfg = json.loads(zipfile.ZipFile(path).read('Metadata/project_settings.config'))
        print(f"{name} | filament={cfg.get('filament_settings_id')} | printer={cfg.get('printer_settings_id')} | process={cfg.get('print_settings_id')}")
    except Exception as e:
        print(f"{name} | ERR {type(e).__name__}")
