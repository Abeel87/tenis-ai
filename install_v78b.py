from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"OK already: {label}")
        return
    if old not in text:
        raise SystemExit(f"STOP: anchor not found for {label}: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"PATCHED: {label}")


update = ROOT / "backend" / "update.py"
replace_once(
    update,
    "from prediction_integrity_v78a import apply_pre_output_guards\n",
    "from prediction_integrity_v78a import apply_pre_output_guards\nfrom joint_builder_v78b import add_joint_builder\n",
    "update import Joint Builder",
)
replace_once(
    update,
    "analysed=[apply_pre_output_guards(analyse_match(long_df,m)) for m in fixtures]",
    "analysed=[add_joint_builder(apply_pre_output_guards(analyse_match(long_df,m))) for m in fixtures]",
    "update attach Joint Builder",
)

integrity = ROOT / "backend" / "prediction_integrity_v78a.py"
text = integrity.read_text(encoding="utf-8")
marker = '    tag = f"{match.get(\'p1\',\'?\')} vs {match.get(\'p2\',\'?\')} [{match.get(\'id\',\'?\')}]"\n'
block = '''    joint = match.get("joint_builder_v78b")
    if joint:
        try:
            from joint_builder_v78b import validate_joint_builder
            for err in validate_joint_builder(joint):
                errors.append(f"{tag}: Joint Builder v7.8B — {err}")
        except Exception as exc:
            errors.append(f"{tag}: Joint Builder v7.8B validator error: {type(exc).__name__}")
'''
if "Joint Builder v7.8B validator error" in text:
    print("OK already: integrity Joint Builder check")
else:
    if marker not in text:
        raise SystemExit("STOP: integrity checker anchor not found")
    text = text.replace(marker, marker + "\n" + block, 1)
    integrity.write_text(text, encoding="utf-8")
    print("PATCHED: integrity Joint Builder check")

print("v7.8B installer complete")
