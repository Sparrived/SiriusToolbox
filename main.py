from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def main() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    from sirius_toolbox.app import run

    argv = sys.argv[1:]
    if not argv:
        argv = ["webui"]

    run(argv)


if __name__ == "__main__":
    main()
