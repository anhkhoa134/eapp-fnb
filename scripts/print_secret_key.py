#!/usr/bin/env python3
"""
Print a new random SECRET_KEY for Django.
./scripts/print_secret_key.py
python scripts/print_secret_key.py --length 64
python scripts/print_secret_key.py --length 50
"""

import argparse
import secrets
import string

ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"


def generate_secret_key(length: int = 64) -> str:
    if length < 50:
        raise ValueError("Length must be at least 50 for production safety.")
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a new Django SECRET_KEY.")
    parser.add_argument(
        "-l",
        "--length",
        type=int,
        default=64,
        help="Secret key length (min: 50, default: 64).",
    )
    args = parser.parse_args()
    print(generate_secret_key(args.length))


if __name__ == "__main__":
    main()
