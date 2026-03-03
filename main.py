from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_db, close_db
from auth import seed_admin
from routes.users import router as users_router
from routes.sites import router as sites_router
from routes.labours import router as labours_router
from routes.attendance import router as attendance_router
from routes.expenses import router as expenses_router
from routes.advances import router as advances_router
from routes.allocations import router as allocations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await seed_admin()
    yield
    await close_db()


app = FastAPI(
    title="Junaidi Builders API",
    description="Construction Contractor Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users_router)
app.include_router(sites_router)
app.include_router(labours_router)
app.include_router(attendance_router)
app.include_router(expenses_router)
app.include_router(advances_router)
app.include_router(allocations_router)


@app.get("/")
async def root():
    return {"message": "Junaidi Builders API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
