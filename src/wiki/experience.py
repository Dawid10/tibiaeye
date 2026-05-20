"""Tibia experience formula."""


def experience_for_level(level):
    """Total cumulative XP needed to reach a level."""
    return (50 * level ** 3 - 300 * level ** 2 + 850 * level - 600) // 3


def level_from_experience(xp):
    """Calculate level from total experience (binary search)."""
    low, high = 1, 50000
    while low < high:
        mid = (low + high + 1) // 2
        if experience_for_level(mid) <= xp:
            low = mid
        else:
            high = mid - 1
    return low


def experience_to_next_level(current_xp):
    """XP remaining to reach the next level."""
    current_level = level_from_experience(current_xp)
    return experience_for_level(current_level + 1) - current_xp
