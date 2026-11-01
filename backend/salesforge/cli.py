"""salesforge pipeline | migrate | seed"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "seed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="salesforge")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pipeline", help="generate data, detect and prioritise opportunities, write data/seed/")
    p.add_argument("--out", type=Path, default=DEFAULT_DATA)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--skip-evaluation", action="store_true")
    sub.add_parser("migrate", help="apply database migrations")
    s = sub.add_parser("seed", help="replace the database contents with data/seed/")
    s.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "pipeline":
        from .pipeline.run import run

        run(args.out, seed=args.seed, with_evaluation=not args.skip_evaluation)
    elif args.command == "migrate":
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    elif args.command == "seed":
        from .db import get_engine
        from .seed import seed

        seed(get_engine(), args.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
