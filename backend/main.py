"""CineMatch API: MovieLens catalog, user accounts, recommendations, and admin aggregates."""
from functools import lru_cache
import re
import sqlite3
from typing import Dict
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from .auth import (SESSION_COOKIE, admin_user, clear_session_cookie,
                   current_user, hash_password, issue_session, set_session_cookie, verify_password)
from .database import connect
from .data_loader import DatasetMissingError, catalog, load_data, movie_dict
from .evaluation import evaluate
from .recommender import recommend

app = FastAPI(title="CineMatch API", description="MovieLens item-based collaborative filtering mini-project")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])


@lru_cache(maxsize=1)
def dataset():
    try:
        return load_data()
    except (DatasetMissingError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def catalog_rows():
    movies, ratings = dataset()
    frame = catalog(movies, ratings)
    return frame, {int(row.movieId): row for row in frame.itertuples(index=False)}


def popular_rows(frame, limit=12):
    # A minimum count makes the actual MovieLens average less noisy.
    selected = frame[frame.rating_count >= 25].sort_values(
        ["dataset_rating", "rating_count"], ascending=False).head(limit)
    return [movie_dict(row) for row in selected.itertuples(index=False)]


def profile_recommendations(user, frame, by_id, rating_data, user_ratings):
    if not user_ratings:
        results = popular_rows(frame)
        mode = "popular"
        message = "You haven't rated any movies yet, so we're showing popular picks. Rate a few movies to get recommendations tailored to your taste."
    elif len(user_ratings) < 2:
        results = [m for m in popular_rows(frame, 16) if m["movieId"] not in user_ratings][:12]
        mode = "insufficient"
        message = "You have started rating movies, but need at least two matching ratings for personalized picks. These popular suggestions are based on MovieLens ratings."
    else:
        recs, info = recommend(rating_data, user_ratings, limit=12, minimum_ratings=2)
        results = []
        for movie_id, score, supports in recs:
            row = by_id.get(movie_id)
            if row is None:
                continue
            item = movie_dict(row)
            titles = [str(by_id[mid].title) for mid, _ in supports if mid in by_id]
            item.update({"predicted_rating": round(score, 2), "support_movies": titles,
                         "explanation": "Similar rating patterns to " + ", ".join(titles) if titles else "Estimated from your ratings."})
            results.append(item)
        mode = "personalized" if results else "no_support"
        message = "" if results else "There is not enough shared rating history to support recommendations yet. Rate a few more movies from different genres."
    # Count actual titles returned, not visits or requests.
    with connect() as db:
        db.execute("INSERT INTO recommendation_events(user_id,generated_count) VALUES(?,?)",
                   (user["id"], len(results)))
    return {"mode": mode, "message": message, "recommendations": results}


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RatingRequest(BaseModel):
    movieId: int = Field(gt=0)
    rating: float = Field(ge=0.5, le=5)

    @field_validator("rating")
    @classmethod
    def half_stars(cls, value):
        if round(value * 2) != value * 2:
            raise ValueError("Ratings must use half-star increments.")
        return value


@app.get("/api/health")
def health():
    try:
        movies, ratings = dataset()
        return {"status": "ok", "dataset": "MovieLens Latest Small", "movies": len(movies), "ratings": len(ratings)}
    except HTTPException as exc:
        return {"status": "dataset_missing", "detail": exc.detail}


@app.post("/api/auth/register")
def register(body: RegisterRequest, response: Response):
    try:
        with connect() as db:
            cursor = db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'user')",
                                (body.name, body.email, hash_password(body.password)))
            user = {"id": cursor.lastrowid, "name": body.name, "email": body.email, "role": "user"}
    except sqlite3.IntegrityError as exc:
        if "users.email" in str(exc):
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
        raise HTTPException(status_code=400, detail="Could not create the account.") from exc
    set_session_cookie(response, issue_session(user["id"]))
    return {"user": user}


@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response):
    with connect() as db:
        row = db.execute("SELECT id,name,email,role,password_hash FROM users WHERE email=? COLLATE NOCASE",
                         (body.email.strip(),)).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user = {key: row[key] for key in ("id", "name", "email", "role")}
    set_session_cookie(response, issue_session(user["id"]))
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        import hashlib
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
    clear_session_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"user": user}


@app.get("/api/movies")
def movies(q: str = Query(default="", max_length=120), limit: int = Query(default=100, ge=1, le=500)):
    movie_data, _ = catalog_rows()
    if q.strip():
        movie_data = movie_data[movie_data.title.str.contains(q.strip(), case=False, regex=False)]
    return [movie_dict(row) for row in movie_data.sort_values("title").head(limit).itertuples(index=False)]


@app.get("/api/popular")
def popular(limit: int = Query(default=24, ge=1, le=100)):
    movie_data, _ = catalog_rows()
    return popular_rows(movie_data, limit)


@app.get("/api/profile")
def profile(user=Depends(current_user)):
    movie_data, by_id = catalog_rows()
    _, rating_data = dataset()
    with connect() as db:
        user_rows = db.execute("SELECT movie_id,rating,updated_at FROM ratings WHERE user_id=? ORDER BY updated_at DESC",
                               (user["id"],)).fetchall()
    user_ratings = {int(row["movie_id"]): float(row["rating"]) for row in user_rows}
    rated_movies = []
    for row in user_rows:
        item = by_id.get(int(row["movie_id"]))
        if item is not None:
            value = movie_dict(item)
            value["user_rating"] = float(row["rating"])
            rated_movies.append(value)
    recommendations = profile_recommendations(user, movie_data, by_id, rating_data, user_ratings)
    return {"user": user, "ratings": rated_movies, **recommendations}


@app.post("/api/profile/ratings")
def save_rating(body: RatingRequest, user=Depends(current_user)):
    _, by_id = catalog_rows()
    if body.movieId not in by_id:
        raise HTTPException(status_code=404, detail="Movie was not found in the MovieLens dataset.")
    with connect() as db:
        db.execute("""INSERT INTO ratings(user_id,movie_id,rating) VALUES(?,?,?)
            ON CONFLICT(user_id,movie_id) DO UPDATE SET rating=excluded.rating,updated_at=CURRENT_TIMESTAMP""",
            (user["id"], body.movieId, body.rating))
    return {"ok": True}


@app.delete("/api/profile/ratings/{movie_id}")
def remove_rating(movie_id: int, user=Depends(current_user)):
    with connect() as db:
        db.execute("DELETE FROM ratings WHERE user_id=? AND movie_id=?", (user["id"], movie_id))
    return {"ok": True}


@app.get("/api/evaluation")
@lru_cache(maxsize=1)
def evaluation():
    _, rating_data = dataset()
    try:
        return evaluate(rating_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="The installed dataset does not have enough ratings to evaluate.") from exc


@app.get("/api/admin/stats")
def admin_stats(_user=Depends(admin_user)):
    movies_data, ratings_data = dataset()
    with connect() as db:
        users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        ratings = db.execute("SELECT COUNT(*) FROM ratings").fetchone()[0]
        recommendations = db.execute("SELECT COALESCE(SUM(generated_count),0) FROM recommendation_events").fetchone()[0]
    return {"total_users": users, "total_user_ratings": ratings,
            "total_movies": len(movies_data), "total_recommendations_generated": recommendations}
