from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, quizzes, sessions, results, users, admin

app = FastAPI(title="Quizzler API", version="1.0.0", description="API for the Quizzler online quiz platform")

# CORS middleware for cross-origin requests (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],  
)

# Include routers with prefixes and tags
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(quizzes.router, prefix="/quizzes", tags=["Quizzes"])
app.include_router(sessions.router, prefix="/quizzes", tags=["Quiz Sessions"])  
app.include_router(results.router, prefix="/results", tags=["Results"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

# Add trivia route at root level for easy access
@app.get("/trivia", tags=["Quizzes"])
async def get_trivia_quizzes_root(topic: str = None, difficulty: str = None, sort_by: str = "popularity"):
    """Get public trivia quizzes (root level endpoint)"""
    from app.routes.quizzes import get_trivia_quizzes
    return await get_trivia_quizzes(topic=topic, difficulty=difficulty, sort_by=sort_by)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Quizzler API", "version": app.version}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)