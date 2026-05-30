"""コマンドラインエントリ。

  python -m fukuoka_gtfs.cli all        # download → build → validate
  python -m fukuoka_gtfs.cli download
  python -m fukuoka_gtfs.cli build
  python -m fukuoka_gtfs.cli validate [--download-tools] [--skip-canonical]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import assembler, downloader, validate
from .config import Config
from .errors import FukuokaGtfsError

# 既定のリポジトリルート = このファイルから 2 つ上（src/fukuoka_gtfs/cli.py → repo）
DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )


def cmd_download(config: Config, _args) -> int:
    downloader.download_all(config)
    return 0


def cmd_build(config: Config, _args) -> int:
    stats = assembler.assemble(config)
    validate.assert_integrity(Path(stats["out_dir"]))
    print(f"✓ GTFS 生成: {stats['zip']}  (trips={stats['trips']}, stop_times={stats['stop_times']})")
    return 0


def cmd_validate(config: Config, args) -> int:
    out_dir = config.build_dir / "gtfs"
    validate.assert_integrity(out_dir)
    if args.skip_canonical:
        print("✓ Python 整合検査のみ実施（Canonical はスキップ）")
        return 0
    counts = validate.run_canonical(
        config.build_dir / "feed.zip", config.build_dir / "validation",
        config.tools_dir, download_tools=args.download_tools,
    )
    errors = counts.get("ERROR", 0)
    print(f"検証結果: {counts}")
    if errors:
        print(f"✗ Canonical Validator が ERROR を {errors} 件報告しました", file=sys.stderr)
        return 1
    print("✓ Canonical Validator: ERROR 0 件")
    return 0


def cmd_all(config: Config, args) -> int:
    downloader.download_all(config)
    stats = assembler.assemble(config)
    validate.assert_integrity(Path(stats["out_dir"]))
    if not args.skip_canonical:
        counts = validate.run_canonical(
            config.build_dir / "feed.zip", config.build_dir / "validation",
            config.tools_dir, download_tools=args.download_tools,
        )
        if counts.get("ERROR", 0):
            print(f"✗ Canonical Validator ERROR {counts['ERROR']} 件", file=sys.stderr)
            return 1
    print(f"✓ 完了: {stats['zip']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fukuoka-gtfs", description="福岡市地下鉄 時刻表→GTFS-JP 生成")
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="リポジトリルート")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("download", help="時刻表 Excel を取得").set_defaults(func=cmd_download)
    sub.add_parser("build", help="GTFS を生成").set_defaults(func=cmd_build)

    pv = sub.add_parser("validate", help="GTFS を検証")
    pv.add_argument("--download-tools", action="store_true", help="JRE/validator を自動取得")
    pv.add_argument("--skip-canonical", action="store_true", help="Python 整合検査のみ")
    pv.set_defaults(func=cmd_validate)

    pa = sub.add_parser("all", help="download→build→validate")
    pa.add_argument("--download-tools", action="store_true")
    pa.add_argument("--skip-canonical", action="store_true")
    pa.set_defaults(func=cmd_all)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    config = Config(args.root)
    try:
        return args.func(config, args)
    except FukuokaGtfsError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
