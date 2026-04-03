#!/usr/bin/env python3
# Script này dùng để reset lại project Django về trạng thái sạch (clean state).
# Thường bao gồm việc xóa cơ sở dữ liệu cũ, tạo lại migrations, làm mới secret key, 
# và có thể tạo lại tài khoản quản trị mặc định để thuận tiện cho việc phát triển/test.
from __future__ import annotations

import argparse
import os
import secrets
import string
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


LOCAL_APPS = [
    "App_Base",
    "App_Account",
    "App_Product",
    "App_Post",
    "App_Cart",
    "App_Order",
    "App_Quanly",
]

DEFAULT_QUANLY_USERNAME = "quanly"
DEFAULT_QUANLY_PASSWORD = "abcdabcd"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "abc"


def generate_secret_key(length: int = 50) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def rm_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def run(cmd: list[str]) -> None:
    print(f"\n$ {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))


def delete_migrations(app_name: str) -> None:
    mig_dir = PROJECT_ROOT / app_name / "migrations"
    if not mig_dir.exists():
        return
    for p in mig_dir.glob("*.py"):
        if p.name == "__init__.py":
            continue
        rm_path(p)
    # cleanup compiled caches if any
    rm_path(mig_dir / "__pycache__")

def ensure_quanly_user(python: str) -> None:
    code = f"""
from django.contrib.auth import get_user_model

User = get_user_model()
u, created = User.objects.get_or_create(
    username={DEFAULT_QUANLY_USERNAME!r},
    defaults={{"is_active": True}},
)
u.is_active = True
u.set_password({DEFAULT_QUANLY_PASSWORD!r})
u.save()
print(("Created" if created else "Updated") + " user:", u.username)
"""
    run([python, "manage.py", "shell", "-c", code.strip()])


def ensure_superadmin_user(python: str) -> None:
    code = f"""
from django.contrib.auth import get_user_model

User = get_user_model()
u, created = User.objects.get_or_create(
    username={DEFAULT_ADMIN_USERNAME!r},
    defaults={{"is_active": True, "is_staff": True, "is_superuser": True}},
)
u.is_active = True
u.is_staff = True
u.is_superuser = True
u.set_password({DEFAULT_ADMIN_PASSWORD!r})
u.save()
print(("Created" if created else "Updated") + " superuser:", u.username)
"""
    run([python, "manage.py", "shell", "-c", code.strip()])

def regenerate_requirements(python: str) -> None:
    req_path = PROJECT_ROOT / "requirements.txt"
    print("\n$ python -m pip freeze > requirements.txt")
    out = subprocess.check_output([python, "-m", "pip", "freeze"], cwd=str(PROJECT_ROOT))
    req_path.write_bytes(out)
    print(f"Wrote: {req_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset dev database/media/logs & regenerate migrations.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run without confirmation prompt.",
    )
    parser.add_argument(
        "--keep-media",
        action="store_true",
        help="Do not delete media/ folder.",
    )
    parser.add_argument(
        "--keep-logs",
        action="store_true",
        help="Do not delete logs/ folder and *.log files.",
    )
    args = parser.parse_args()

    if not args.yes:
        print("This will DELETE:")
        print("- db.sqlite3")
        print("- migrations for local apps:", ", ".join(LOCAL_APPS))
        if not args.keep_media:
            print("- media/")
        if not args.keep_logs:
            print("- logs/ and *.log")
        print()
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return 1

    # 1) delete sqlite db
    rm_path(PROJECT_ROOT / "db.sqlite3")

    # 2) delete migrations (local apps only)
    for app in LOCAL_APPS:
        delete_migrations(app)

    # 3) delete media + logs
    if not args.keep_media:
        rm_path(PROJECT_ROOT / "media")
        (PROJECT_ROOT / "media").mkdir(parents=True, exist_ok=True)

    if not args.keep_logs:
        rm_path(PROJECT_ROOT / "logs")
        (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)
        for log_file in PROJECT_ROOT.rglob("*.log"):
            # avoid deleting logs inside venv if user has any
            if "venv" in log_file.parts or "env" in log_file.parts:
                continue
            rm_path(log_file)

    # 4) delete common caches
    for p in PROJECT_ROOT.rglob("__pycache__"):
        rm_path(p)
    for cache_dir in [".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov"]:
        rm_path(PROJECT_ROOT / cache_dir)

    # 5) re-generate & migrate
    python = sys.executable
    run([python, "manage.py", "makemigrations"])
    run([python, "manage.py", "migrate"])
    ensure_quanly_user(python)
    ensure_superadmin_user(python)
    regenerate_requirements(python)

    new_secret_key = generate_secret_key()
    print("\nDone.")
    print(f"\nNEW SECRET_KEY:\n{new_secret_key}\n")
    print(f"DEFAULT QUANLY LOGIN: {DEFAULT_QUANLY_USERNAME} / {DEFAULT_QUANLY_PASSWORD}")
    print(f"DEFAULT SUPERADMIN LOGIN: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

