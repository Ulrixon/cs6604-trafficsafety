from pydantic import BaseModel, Field, RootModel


class IntersectionBase(BaseModel):
    """
    Shared fields for Intersection schemas.
    """

    intersection_name: str = Field(..., example="Glebe & Potomac")
    safety_index: float = Field(..., ge=0, le=100, example=63.0)
    traffic_volume: int = Field(..., ge=0, example=253)
    longitude: float = Field(..., example=-77.053)
    latitude: float = Field(..., example=38.856)


class IntersectionRead(IntersectionBase):
    """
    Schema returned to the client.
    """

    intersection_id: int = Field(..., example=101)


# Optional: list wrapper (FastAPI can also use List[IntersectionRead] directly)
class IntersectionList(RootModel[list[IntersectionRead]]):
    pass
