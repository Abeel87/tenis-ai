from pathlib import Path

src = Path(".github/workflows/v85_install.py").read_text(encoding="utf-8")
src = src.replace(
    "for rel in ('v85_install.py','.github/workflows/install-v85.yml'):",
    "for rel in ('v85_install.py',):"
)

exec(
    compile(src, "v85_install.py", "exec"),
    {
        "__name__": "__main__",
        "__file__": str(Path.cwd() / "v85_install.py"),
    },
)
