from dataclasses import dataclass
from typing import Optional


@dataclass
class Intersection:
    """
    Domain model representing a traffic intersection.
    """

    intersection_id: int
    intersection_name: str
    safety_index: Optional[float]  # Can be None if no safety data available
    traffic_volume: int
    longitude: float
    latitude: float
