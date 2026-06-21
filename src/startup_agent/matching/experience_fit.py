def experience_penalty(user_years: int | None, required_years: int | None) -> int:
    """Points to subtract from a 0-100 fit score for an experience mismatch.

    Asymmetric: under-qualification (job needs more than the candidate has) is a
    far bigger barrier than over-qualification. Returns 0 when either side is unknown.
    """
    if user_years is None or required_years is None:
        return 0
    gap = required_years - user_years  # >0 underqualified, <0 overqualified
    if gap >= 6:
        return 50
    if gap >= 4:
        return 30
    if gap >= 2:
        return 15
    if gap >= -2:        # -2..1 -> well matched / trivial stretch
        return 0
    if gap >= -5:        # 3-5 years over
        return 5
    return 12            # 6+ years over
