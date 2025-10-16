from dataclasses import dataclass


@dataclass
class Intersection:
    """
    Domain model representing a traffic intersection.
    """

    intersection_id: int
    intersection_name: str
    safety_index: float
    traffic_volume: int
    longitude: float
    latitude: float
