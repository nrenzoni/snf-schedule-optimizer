from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PKG = (ROOT / "../snf-schedule-optimizer-service/src/snf_schedule_optimizer").resolve()
OUT = (PKG / "generated").resolve()

# ensure package files exist
for d in [OUT] + [p for p in OUT.rglob("*") if p.is_dir()]:
    init = d / "__init__.py"
    if not init.exists():
        init.write_text("# generated package\n")

for py_typed in (PKG / "py.typed", OUT / "py.typed"):
    if not py_typed.exists():
        py_typed.write_text("")

# patterns to rewrite
replacements = [
    (re.compile(r"\bimport\s+scheduling\.v1\."), "import snf_schedule_optimizer.generated.scheduling.v1."),
    (re.compile(r"\bfrom\s+scheduling\.v1\."), "from snf_schedule_optimizer.generated.scheduling.v1."),
    # handle other scheduling.v1.* variants if present
]

changed = 0
for py in OUT.rglob("*.py"):
    text = py.read_text(encoding="utf-8")
    new_text = text
    for patt, rep in replacements:
        new_text = patt.sub(rep, new_text)
    if new_text != text:
        py.write_text(new_text, encoding="utf-8")
        changed += 1

print(f"Patched {changed} files under {OUT}")
