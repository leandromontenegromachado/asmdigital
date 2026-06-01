from __future__ import annotations

import argparse
import json
from pathlib import Path

from .advisor import evaluate_project
from .models import ProjectSnapshot
from .redmine_client import RedmineClient
from .render import render_json, render_markdown


def load_snapshot_from_file(path: Path) -> ProjectSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectSnapshot.from_json(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agente consultivo somente leitura para projetos Redmine.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--project-id", help="ID ou identificador do projeto no Redmine.")
    source.add_argument("--input", type=Path, help="Arquivo JSON local com dados do projeto.")
    parser.add_argument("--days-stale", type=int, default=7, help="Dias sem atualização para considerar uma issue parada.")
    parser.add_argument("--output", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    if args.input:
        snapshot = load_snapshot_from_file(args.input)
    else:
        snapshot = RedmineClient.from_env().get_project_snapshot(args.project_id)

    report = evaluate_project(snapshot, days_stale=args.days_stale)
    if args.output == "json":
        print(render_json(report))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
