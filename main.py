"""Project Intelligence — CLI Entry Point.

Sử dụng:
    python main.py /đường/dẫn/repo              # Chạy pipeline (fast mode)
    python main.py /đường/dẫn/repo --mode deep  # Chạy pipeline (deep mode — multi-agent)
    python main.py /đường/dẫn/repo --serve      # Pipeline + khởi động API
    python main.py --serve                       # Chỉ khởi động API (dùng index có sẵn)
"""

import sys
import os
import argparse

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="🧠 Repo Knowledge System — Tạo knowledge base từ code repository bằng AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python main.py /path/to/my-project                     Fast mode (mặc định)
  python main.py /path/to/my-project --mode deep         Deep mode (multi-agent crew)
  python main.py /path/to/my-project --serve             Pipeline + API server
  python main.py --serve                                  Chỉ API server
  python main.py /path/to/repo --output ./out             Chỉ định thư mục output
        """,
    )

    parser.add_argument(
        "repo_path",
        nargs="?",
        help="Đường dẫn đến thư mục repo cần phân tích",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "deep"],
        default="fast",
        help="Chế độ tóm tắt: fast (1 LLM/chunk, mặc định) hoặc deep (multi-agent crew)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Khởi động FastAPI server sau khi chạy pipeline",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Thư mục output (mặc định: ./output)",
    )

    args = parser.parse_args()

    # Validate: cần ít nhất repo_path hoặc --serve
    if not args.repo_path and not args.serve:
        parser.print_help()
        print("\n❌ Cần chỉ định repo_path hoặc --serve")
        sys.exit(1)

    # ─── Chạy pipeline nếu có repo_path ─────────────────────────
    if args.repo_path:
        repo_path = os.path.abspath(args.repo_path)

        if not os.path.isdir(repo_path):
            print(f"❌ Thư mục không tồn tại: {repo_path}")
            sys.exit(1)

        # Import và chạy pipeline
        from pipeline.orchestrator import run_pipeline

        try:
            result = run_pipeline(repo_path, output_dir=args.output, mode=args.mode)
        except Exception as e:
            print(f"\n❌ Lỗi pipeline: {e}")
            sys.exit(1)

    # ─── Khởi động API server nếu --serve ───────────────────────
    if args.serve:
        from api.server import start_server
        from config.settings import API_HOST, API_PORT

        print("=" * 60)
        print("  🌐 Khởi động API server...")
        print(f"  📍 http://{API_HOST}:{API_PORT}")
        print(f"  📍 Docs: http://{API_HOST}:{API_PORT}/docs")
        print("=" * 60)
        print()

        start_server()


if __name__ == "__main__":
    main()