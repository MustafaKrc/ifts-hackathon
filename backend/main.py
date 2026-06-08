from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, SessionLocal, engine
from models import CustomerJourney
from routers import auth, health, journeys


def seed_initial_data():
    db = SessionLocal()
    try:
        if db.query(CustomerJourney).count() > 0:
            return

        db.add_all(
            [
                CustomerJourney(
                    name="Fiber Upsell Journey",
                    segment="High-value household",
                    region="Istanbul",
                    risk_score=18,
                    recommended_action="Highlight fast fiber setup and family bundle benefits.",
                ),
                CustomerJourney(
                    name="Digital Starter Journey",
                    segment="Young professional",
                    region="Ankara",
                    risk_score=42,
                    recommended_action="Promote app-first onboarding with extra data for first month.",
                ),
                CustomerJourney(
                    name="Retention Journey",
                    segment="Contract ending soon",
                    region="Izmir",
                    risk_score=76,
                    recommended_action="Offer loyalty discount and proactive network quality follow-up.",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_initial_data()
    yield


app = FastAPI(
    title="Turkcell Customer Experience API",
    description="FastAPI + SQLite backend for the Turkcell landing and login application.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(journeys.router)
