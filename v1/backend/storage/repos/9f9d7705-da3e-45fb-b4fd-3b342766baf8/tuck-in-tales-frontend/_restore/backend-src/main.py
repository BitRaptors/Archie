from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter
import logging

# Import routers
from src.routes import characters, stories, memories, family

# Import settings
from src.config import settings

# --- Firebase Admin SDK setup ---
from src.utils.firebase_admin_init import initialize_firebase_admin

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

app = FastAPI(
    title="Tuck-In Tales Backend",
    description="API for generating personalized bedtime stories.",
    version="0.1.0",
)

# --- Force Root Logger Level ---
logging.getLogger().setLevel(logging.INFO)
logging.info("Root logger level explicitly set to INFO after app creation.")

# --- CORS Configuration ---
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to Tuck-In Tales API"}

# Include routers under /api prefix
api_router = APIRouter(prefix="/api")

api_router.include_router(characters.router)
api_router.include_router(stories.router)
api_router.include_router(memories.router)
api_router.include_router(family.router)

app.include_router(api_router)
