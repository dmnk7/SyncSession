"""Schreibt bericht/autoren.tex aus den BERICHT_*-Variablen in ../.env."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
OUT_PATH = Path(__file__).resolve().parent / "autoren.tex"

REQUIRED = ("BERICHT_EMAIL_A", "BERICHT_MATRIKEL_A", "BERICHT_EMAIL_B")


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def main() -> int:
    if not ENV_PATH.is_file():
        print(f"Fehlt: {ENV_PATH}", file=sys.stderr)
        return 1
    values = parse_env(ENV_PATH)
    missing = [key for key in REQUIRED if not values.get(key, "").strip()]
    if missing:
        print(
            "In .env fehlen: "
            + ", ".join(missing)
            + " (optional: BERICHT_MATRIKEL_B)",
            file=sys.stderr,
        )
        return 1
    commands = {
        "authorEMailA": values["BERICHT_EMAIL_A"].strip(),
        "authorEnrolmentNoA": values["BERICHT_MATRIKEL_A"].strip(),
        "authorEMailB": values["BERICHT_EMAIL_B"].strip(),
        "authorEnrolmentNoB": values.get("BERICHT_MATRIKEL_B", "").strip(),
    }
    lines = [
        "% Automatisch erzeugt von sync_autoren.py. Nicht einchecken.",
        *(
            f"\\newcommand{{\\{name}}}{{{latex_escape(value)}}}"
            for name, value in commands.items()
        ),
        "",
    ]
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
