# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Normalize album/track release years for storage and API responses."""


def normalize_release_year(year: int | None) -> int | None:
    """Return a real release year, or None when the value is missing/placeholder.

    Tags and imports sometimes store 0 (or a negative number) instead of omitting
    the year. Android clients crash if they render `{year && ...}` when year is 0.
    """
    if year is None or year <= 0:
        return None
    return year
