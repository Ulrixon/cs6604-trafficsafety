from fastapi import APIRouter, HTTPException

from ..schemas.intersection import IntersectionRead
from ..services.intersection_service import get_all, get_by_id

router = APIRouter(prefix="/safety/index", tags=["Safety Index"])


@router.get("/", response_model=list[IntersectionRead])
def list_intersections():
    """
    Retrieve a list of all intersections with their safety index data.
    """
    return get_all()


@router.get("/{intersection_id}", response_model=IntersectionRead)
def get_intersection(intersection_id: int):
    """
    Retrieve details for a single intersection by its ID.
    """
    intersection = get_by_id(intersection_id)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection
