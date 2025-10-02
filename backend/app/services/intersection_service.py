from typing import List, Optional

from ..models.intersection import Intersection

# In‑memory mock data store
_INTERSECTIONS: List[Intersection] = [
    Intersection(
        intersection_id=101,
        intersection_name="Glebe & Potomac",
        safety_index=63.0,
        traffic_volume=253,
        longitude=-77.053,
        latitude=38.856,
    ),
    Intersection(
        intersection_id=102,
        intersection_name="Main St & 1st Ave",
        safety_index=78.5,
        traffic_volume=410,
        longitude=-77.060,
        latitude=38.860,
    ),
    Intersection(
        intersection_id=103,
        intersection_name="Broadway & 5th Ave",
        safety_index=55.2,
        traffic_volume=320,
        longitude=-77.045,
        latitude=38.870,
    ),
    Intersection(
        intersection_id=104,
        intersection_name="Elm St & Oak Rd",
        safety_index=82.1,
        traffic_volume=210,
        longitude=-77.050,
        latitude=38.855,
    ),
    Intersection(
        intersection_id=105,
        intersection_name="Maple Ave & Pine St",
        safety_index=70.4,
        traffic_volume=380,
        longitude=-77.058,
        latitude=38.862,
    ),
]


def get_all() -> List[Intersection]:
    """Return a list of all intersections."""
    return list(_INTERSECTIONS)


def get_by_id(intersection_id: int) -> Optional[Intersection]:
    """Return a single intersection matching the given ID, or None."""
    for item in _INTERSECTIONS:
        if item.intersection_id == intersection_id:
            return item
    return None
