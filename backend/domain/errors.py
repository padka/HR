class CityAlreadyExistsError(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"City '{name}' already exists")


class SlotOverlapError(Exception):
    """Raised when attempting to create a slot that overlaps with an existing slot.

    This is a business-level exception representing a constraint violation
    by the database exclusion constraint: slots_no_recruiter_time_overlap_excl
    """
    def __init__(self, recruiter_id: int, start_utc, end_utc=None):
        self.recruiter_id = recruiter_id
        self.start_utc = start_utc
        self.end_utc = end_utc
        super().__init__(
            f"Recruiter {recruiter_id} already has a slot overlapping with "
            f"{start_utc.isoformat() if hasattr(start_utc, 'isoformat') else start_utc}"
        )


__all__ = ["CityAlreadyExistsError", "SlotOverlapError"]
