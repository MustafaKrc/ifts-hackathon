from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import CustomerJourney
from schemas import CustomerJourneyCreate, CustomerJourneyRead


router = APIRouter(prefix="/api/customer-journeys", tags=["customer journeys"])


@router.get("", response_model=list[CustomerJourneyRead])
def list_customer_journeys(db: Session = Depends(get_db)):
    """Return SQLite-backed customer journey records for the landing page."""
    return db.query(CustomerJourney).order_by(CustomerJourney.risk_score.desc()).all()


@router.post("", response_model=CustomerJourneyRead, status_code=201)
def create_customer_journey(payload: CustomerJourneyCreate, db: Session = Depends(get_db)):
    """Create a customer journey record."""
    journey = CustomerJourney(**payload.model_dump())
    db.add(journey)
    db.commit()
    db.refresh(journey)
    return journey


@router.get("/theme")
def get_theme():
    """Return the brand colors used by the frontend."""
    return {
        "primaryYellow": "#FFD100",
        "navyBlue": "#003087",
        "white": "#FFFFFF",
        "lightGrey": "#F5F5F5",
    }
