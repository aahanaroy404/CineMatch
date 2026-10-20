"""MovieLens CSV loading and dataset-backed catalog helpers."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "ml-latest-small"


class DatasetMissingError(FileNotFoundError):
    pass


def load_data():
    movies_path, ratings_path = DATA_DIR / "movies.csv", DATA_DIR / "ratings.csv"
    if not movies_path.exists() or not ratings_path.exists():
        raise DatasetMissingError(
            "MovieLens data is missing. Download MovieLens Latest Small from "
            "https://grouplens.org/datasets/movielens/latest/ and extract movies.csv and "
            "ratings.csv into data/ml-latest-small/."
        )
    movies = pd.read_csv(movies_path)
    ratings = pd.read_csv(ratings_path)
    required_movies, required_ratings = {"movieId", "title", "genres"}, {"userId", "movieId", "rating"}
    if not required_movies.issubset(movies.columns) or not required_ratings.issubset(ratings.columns):
        raise ValueError("Dataset CSV files do not have the expected MovieLens columns.")
    return movies, ratings


def catalog(movies, ratings):
    stats = ratings.groupby("movieId").rating.agg(dataset_rating="mean", rating_count="count")
    result = movies.merge(stats, on="movieId", how="left")
    result["rating_count"] = result.rating_count.fillna(0).astype(int)
    result["dataset_rating"] = result.dataset_rating.round(2)
    return result


def movie_dict(row):
    title = str(row.title)
    year = None
    if len(title) >= 6 and title[-5:-1].isdigit() and title[-6:-5] == "(":
        year = int(title[-5:-1])
    return {"movieId": int(row.movieId), "title": title, "year": year,
            "genres": str(row.genres).split("|") if row.genres != "(no genres listed)" else [],
            "dataset_rating": None if pd.isna(row.dataset_rating) else float(row.dataset_rating),
            "rating_count": int(row.rating_count)}
