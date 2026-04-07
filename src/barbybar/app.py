from __future__ import annotations

from barbybar.desktop_app import main as desktop_main


def main() -> int:
    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
