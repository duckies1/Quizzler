# Quizzler Backend

A FastAPI-based backend for the Quizzler online quiz platform, built for a college project.

## Setup

1. Clone the repository: `git clone <repository-url>`
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in `.env` with your Supabase credentials.
4. Create database tables by running the SQL from `create_tables.sql` in your Supabase dashboard
5. Run the app: `python app/main.py` or `uvicorn app.main:app --reload`

## API Endpoints

- `/auth/signup`: Register a new user.
- `/auth/login`: Log in and get a token.
- `/quizzes/`: Create a new quiz.
- `/sessions/{quiz_id}/start`: Start a quiz session.
- `/results/{quiz_id}/my-result`: View personal results.
- `/results/{quiz_id}/results`: View host results.

## Notes

- Ensure Supabase is configured with the provided URL and key.
- The frontend (to be built with React) will integrate with these endpoints.
