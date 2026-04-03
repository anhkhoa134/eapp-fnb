#!/usr/bin/env python3
# Script này dùng để loại bỏ tất cả các file đã được cached theo .gitignore khỏi index git,
# sau đó add lại, commit với message tùy chọn và push lên nhánh main của repository.
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], check: bool = True) -> int:
    print(f"\n$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if check and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Loại bỏ toàn bộ cached theo .gitignore, add lại, "
            "commit và git push origin main."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Bỏ qua bước xác nhận.",
    )
    parser.add_argument(
        "-m",
        "--message",
        default="Clean cached files using .gitignore",
        help="Commit message.",
    )
    args = parser.parse_args()

    # Kiểm tra có phải repo git không
    if not (PROJECT_ROOT / ".git").exists():
        print("Không tìm thấy thư mục .git trong project root.")
        return 1

    if not args.yes:
        print("Script này sẽ chạy các bước:")
        print("  1) git rm -r --cached .")
        print("  2) git add .")
        print(f"  3) git commit -m \"{args.message}\"")
        print("  4) git push origin main")
        print()
        confirm = input("Gõ 'yes' để tiếp tục: ").strip().lower()
        if confirm != "yes":
            print("Đã hủy.")
            return 1

    # Hiển thị status trước khi làm
    run(["git", "status"], check=False)

    # Bỏ cache theo .gitignore
    run(["git", "rm", "-r", "--cached", "."], check=False)

    # Add lại các file không bị ignore
    run(["git", "add", "."])

    # Commit; nếu không có gì để commit thì không fail cả script
    ret = run(["git", "commit", "-m", args.message], check=False)
    if ret != 0:
        print("Không có gì để commit hoặc commit bị hủy.")
    else:
        # Chỉ push khi commit thành công
        run(["git", "push"], check=False)

    # Hiển thị status sau khi làm
    run(["git", "status"], check=False)

    print("\nHoàn tất clean cached theo .gitignore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

