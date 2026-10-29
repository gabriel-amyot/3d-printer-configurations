"""Rebuild lost OrcaSlicer user presets from 3MF projects and compare them with current presets.

Usage: python3 -I rebuild_presets.py <3mf_list.txt> <orca_data_dir> <out_dir> [<extra_user_preset.json> ...]

Output:
  <out_dir>/recovered/{filament,machine,process}/<name>.json   importable Orca user presets (newest version)
  <out_dir>/recovered/_older_versions/...                       older variants when a preset changed over time
  <out_dir>/REPORT.md                                          inventory + comparisons
"""
import sys, os, json, re, zipfile, glob, datetime, difflib

list_file, orca_dir, out_dir, *extra_files = sys.argv[1:]
KINDS = [("process", "print_settings_id"), ("filament", "filament_settings_id"), ("machine", "printer_settings_id")]
ID_KEYS = {"process": "print_settings_id", "filament": "filament_settings_id", "machine": "printer_settings_id"}
SKIP_IN_COMPARE = {"name", "from", "inherits", "version", "is_custom_defined", "setting_id", "instantiation",
                   "filament_settings_id", "print_settings_id", "printer_settings_id", "type", "source_project"}


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()


def day(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def short(v, n=60):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    s = s.replace("\n", "\\n").replace("|", "\\|")
    return s if len(s) <= n else s[:n] + "…"


# ---------- system + current user presets (for resolving inheritance) ----------
def load_presets(pattern):
    found = {}
    for p in glob.glob(pattern, recursive=True):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("name"):
            found[d["name"]] = (d, p)
    return found


system = load_presets(os.path.join(orca_dir, "system", "**", "*.json"))
current_user = {}
for kind in ("filament", "machine", "process"):
    for folder in glob.glob(os.path.join(orca_dir, "user", "*")):
        for name, (d, p) in load_presets(os.path.join(folder, kind, "*.json")).items():
            current_user[(kind, name)] = (d, p)


def resolve(name, own=None, depth=0):
    """Flatten a preset through its inherits chain (system presets, then current user presets)."""
    if own is None:
        hit = system.get(name) or next((v for (k, n), v in current_user.items() if n == name), None)
        if not hit:
            return {}, [f"MISSING:{name}"]
        own = hit[0]
    parent = own.get("inherits") or ""
    base, chain = ({}, [])
    if parent and depth < 20:
        base, chain = resolve(parent, None, depth + 1)
    merged = dict(base)
    merged.update({k: v for k, v in own.items() if k not in ("inherits", "name", "from", "instantiation", "type")})
    return merged, [own.get("name", name)] + chain


# ---------- read projects ----------
projects = []
for path in open(list_file).read().splitlines():
    try:
        cfg = json.loads(zipfile.ZipFile(path).read("Metadata/project_settings.config"))
    except Exception:
        continue
    projects.append((os.path.getmtime(path), path, cfg))
projects.sort()


def preset_from_project(cfg, kind, idx_in_group, slot=0):
    """Build an Orca user preset (parent + only the settings that differ) from a project config."""
    groups = cfg.get("inherits_group") or []
    diffs = cfg.get("different_settings_to_system") or []
    names = cfg.get(ID_KEYS[kind])
    name = names[slot] if isinstance(names, list) else names
    if kind == "filament":
        n_fil = len(names) if isinstance(names, list) else 1
        parent = groups[1 + slot] if len(groups) > 1 + slot else ""
        diff_str = diffs[1 + slot] if len(diffs) > 1 + slot else ""
    else:
        n_fil = len(cfg.get("filament_settings_id") or [1])
        pos = 0 if kind == "process" else 1 + n_fil
        parent = groups[pos] if len(groups) > pos else ""
        diff_str = diffs[pos] if len(diffs) > pos else ""
    keys = [k for k in diff_str.split(";") if k]
    preset = {"from": "User", "inherits": parent, "name": name, "version": cfg.get("version", "2.1.1") + ".0"
              if cfg.get("version", "").count(".") == 2 else cfg.get("version", "2.1.1.0")}
    if kind == "filament":
        preset["filament_settings_id"] = [name]
    else:
        preset[ID_KEYS[kind]] = name
    for k in keys:
        if k not in cfg:
            continue
        v = cfg[k]
        if kind == "filament" and isinstance(v, list) and len(v) == n_fil:
            v = [v[slot]]
        preset[k] = v
    if not parent:
        # No system parent recorded: keep the full config so nothing is lost.
        for k, v in cfg.items():
            preset.setdefault(k, [v[slot]] if kind == "filament" and isinstance(v, list) and len(v) == n_fil else v)
    return name, preset, keys


versions = {}  # (kind, name) -> list of (mtime, project, preset, tuned_keys, full_cfg)
for mtime, path, cfg in projects:
    for kind, key in KINDS:
        names = cfg.get(key)
        slots = range(len(names)) if isinstance(names, list) else [0]
        for slot in slots:
            name, preset, keys = preset_from_project(cfg, kind, 0, slot)
            if not name:
                continue
            versions.setdefault((kind, name), []).append((mtime, path, preset, keys, cfg))

for f in extra_files:
    d = json.load(open(f))
    kind = "filament" if "filament_settings_id" in d else ("machine" if "printer_settings_id" in d else "process")
    keys = [k for k in d if k not in SKIP_IN_COMPARE]
    versions.setdefault((kind, d["name"]), []).append((os.path.getmtime(f), f + " (VS Code history)", d, keys, None))


def is_stock(kind, name, entries):
    return name in system and all(not e[3] for e in entries)


def strip_meta(p):
    return {k: v for k, v in p.items() if k not in ("version",)}


# ---------- write recovered presets ----------
rec_dir = os.path.join(out_dir, "recovered")
rows, details = [], []
for (kind, name), entries in sorted(versions.items(), key=lambda x: (x[0][0], x[0][1].lower())):
    entries.sort(key=lambda e: e[0])
    stock = is_stock(kind, name, entries)
    foreign = not entries[-1][2].get("inherits") and "/Downloads/" in entries[-1][1]
    edited_stock = (not stock) and name in system
    if foreign:
        rows.append(f"| {kind} | {name} | — | — | {len(entries)} | — | — | skipped: from a downloaded project, not yours |")
        continue
    if edited_stock:
        for e in entries:
            e[2]["name"] = name + " (my edits)"
            e[2][ID_KEYS[kind]] = [e[2]["name"]] if kind == "filament" else e[2]["name"]
    variants = []
    for e in entries:
        if not variants or strip_meta(variants[-1][2]) != strip_meta(e[2]):
            variants.append(e)
    latest = entries[-1]
    if not stock:
        os.makedirs(os.path.join(rec_dir, kind), exist_ok=True)
        json.dump(latest[2], open(os.path.join(rec_dir, kind, safe(latest[2]["name"]) + ".json"), "w"), indent=4)
        for i, v in enumerate(variants[:-1], 1):
            od = os.path.join(rec_dir, "_older_versions", kind)
            os.makedirs(od, exist_ok=True)
            json.dump(v[2], open(os.path.join(od, f"{safe(v[2]['name'])} (v{i} {day(v[0])}).json"), "w"), indent=4)
    on_disk = (kind, name) in current_user
    status = "stock Orca preset (not lost)" if stock else ("still on disk" if on_disk else ("**unsaved edits on stock preset → recovered as `" + name + " (my edits)`**" if edited_stock else "**LOST → recovered**"))
    rows.append(f"| {kind} | {name} | {latest[2].get('inherits', '')} | {len(latest[3])} | {len(entries)} | "
                f"{day(entries[0][0])} → {day(latest[0])} | {len(variants)} | {status} |")
    if stock:
        continue

    # Details: tuned settings vs stock parent
    sec = [f"\n### {kind}: {name}\n",
           f"- Rebuilt from: `{os.path.basename(latest[1])}` ({day(latest[0])}). Used in {len(entries)} project(s).",
           f"- Stock parent: `{latest[2].get('inherits') or 'none recorded'}`\n"]
    parent_full, chain = resolve(latest[2].get("inherits", "")) if latest[2].get("inherits") else ({}, [])
    if any(c.startswith("MISSING:") for c in chain):
        sec.append(f"> Parent chain not fully found in this Orca install: {chain}\n")
    sec.append("| Setting you tuned | Stock value | Your value |\n|---|---|---|")
    for k in latest[3]:
        sec.append(f"| `{k}` | {short(parent_full.get(k, '—'))} | {short(latest[2].get(k, '—'))} |")

    if len(variants) > 1:
        sec.append(f"\n**This preset changed over time ({len(variants)} versions).** Changes between versions:\n")
        sec.append("| Setting | " + " | ".join(f"v{i+1} {day(v[0])} ({os.path.basename(v[1])})" for i, v in enumerate(variants)) + " |")
        sec.append("|---|" + "---|" * len(variants))
        allk = sorted(set().union(*[set(v[2]) for v in variants]) - SKIP_IN_COMPARE)
        for k in allk:
            vals = [v[2].get(k, "(stock)") for v in variants]
            if any(x != vals[0] for x in vals):
                sec.append(f"| `{k}` | " + " | ".join(short(x, 40) for x in vals) + " |")

    # Compare with the closest preset that exists in Orca now
    cands = [n for (k2, n) in current_user if k2 == kind]
    base_name = re.sub(r"\s*@\S+|\(.*?\)", "", name).strip().lower()
    best = max(cands, key=lambda n: difflib.SequenceMatcher(None, base_name, n.lower()).ratio(), default=None)
    if best:
        cur_own, cur_path = current_user[(kind, best)]
        cur_full, _ = resolve(best)
        rec_full = dict(parent_full)
        rec_full.update({k: v for k, v in latest[2].items()})
        cur_keys = [k for k in cur_own if k not in SKIP_IN_COMPARE]
        keys = sorted((set(latest[3]) | set(cur_keys)) - SKIP_IN_COMPARE)
        sec.append(f"\n**Compared with the closest current preset: `{best}`** "
                   f"(`{os.path.relpath(cur_path, orca_dir)}`, parent `{cur_own.get('inherits', '')}`)\n")
        sec.append("| Setting | Recovered | Current | Same? |\n|---|---|---|---|")
        for k in keys:
            a, b = rec_full.get(k, "—"), cur_full.get(k, "—")
            sec.append(f"| `{k}` | {short(a, 45)} | {short(b, 45)} | {'✅' if a == b else '❌'} |")
    details.append("\n".join(sec))

# ---------- names Orca remembers that exist nowhere ----------
conf = json.load(open(os.path.join(orca_dir, "OrcaSlicer.conf"))) if os.path.exists(os.path.join(orca_dir, "OrcaSlicer.conf")) else {}
remembered = set()
for p in conf.get("orca_presets", []):
    for kind, key in (("filament", "filament"), ("machine", "machine"), ("process", "process")):
        if p.get(key):
            remembered.add((kind, p[key]))
known = set(versions) | set(current_user) | {(k, n) for k in ("filament", "machine", "process") for n in system}
ghosts = sorted(n for n in remembered - known if ".3mf)" not in n[1])

with open(os.path.join(out_dir, "REPORT.md"), "w") as f:
    f.write("# OrcaSlicer preset recovery report\n\n")
    f.write(f"Generated {datetime.date.today()}. Scanned {len(projects)} projects.\n\n")
    f.write("## Inventory\n\n| Type | Preset | Stock parent | Tuned settings | Projects | First → last use | Versions | Status |\n"
            "|---|---|---|---|---|---|---|---|\n")
    f.write("\n".join(rows) + "\n")
    f.write("\n## Names Orca remembers, but no project or file holds\n\n")
    f.write("\n".join(f"- {k}: `{n}`" for k, n in ghosts) or "- none")
    f.write("\n\n## Details\n")
    f.write("\n".join(details) + "\n")

print("\n".join(rows))
print("\nGhosts:", ghosts)
