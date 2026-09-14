#!/usr/bin/env python3
"""Safe Replit entry point: validate and display the authoritative library."""

from verify_bundle import validate


def main() -> None:
    manifest = validate()
    print("Infinite Arch Photo Lab migration bundle")
    print("Authoritative Leica release: v1.2")
    print("Offline validation: PASS")
    print()
    for look in manifest:
        print(f"{look['id']}: {look['name']} ({look['base_name']})")
    print()
    print("No camera connection was attempted.")
    print("Read START_HERE.md before development or camera operations.")


if __name__ == "__main__":
    main()

