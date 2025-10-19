from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, quizzes, sessions, results

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
app.include_router(sessions.router, prefix="/sessions", tags=["Quiz Sessions"])
app.include_router(results.router, prefix="/results", tags=["Results"])

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Quizzler API", "version": app.version}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)