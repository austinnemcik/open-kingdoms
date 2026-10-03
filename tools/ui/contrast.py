"""Print WCAG contrast ratios for the text/background pairs the UI uses.

    python tools/ui/contrast.py

Body text must be >= 4.5:1 (see docs/UI_STYLE.md, "Accessibility"). Exits
non-zero if any pair falls below that.
"""

from __future__ import annotations

import sys

MINIMUM = 4.5

# (label, text colour, background colour)
PAIRS = [
    ("TEXT on wood", "fff6e0", "463020"),
    ("TEXT_MUTED on wood", "d9c7a3", "463020"),
    ("TEXT_GOLD on wood", "ffd978", "463020"),
    ("DANGER on wood", "ff8a78", "463020"),
    ("SUCCESS on wood", "9be063", "463020"),
    ("WARNING on wood", "ffc24a", "463020"),
    ("INK on parchment", "2e2014", "f1e3c4"),
    ("INK_MUTED on parchment", "6b543a", "f1e3c4"),
    ("INK_MUTED on parchment edge", "6b543a", "e2cc9d"),
    ("INK_DANGER on parchment", "b3261e", "f1e3c4"),
    ("INK_SUCCESS on parchment", "276a1c", "f1e3c4"),
    ("placeholder on field", "7a6444", "fbf3de"),
    ("gold button label", "4a2c0a", "e3961d"),
    ("selected tab label", "4a2c0a", "f0b93c"),
    ("unselected tab label", "d9c7a3", "432e1f"),
    ("button label on neutral (darkest)", "fff6e0", "1f5f6e"),
    ("tooltip text", "fff6e0", "1d1410"),
]


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def main() -> None:
    failed = False
    for label, text, background in PAIRS:
        ratio = contrast(text, background)
        ok = ratio >= MINIMUM
        failed = failed or not ok
        print(f"{'ok  ' if ok else 'FAIL'} {ratio:5.2f}  {label}  (#{text} on #{background})")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
