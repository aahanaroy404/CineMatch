"""Reproducible held-out evaluation without train/test leakage."""
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from .recommender import build_similarity, predict_from_matrix


def evaluate(ratings, test_size=0.2, seed=42):
    train, test = train_test_split(ratings, test_size=test_size, random_state=seed)
    train_matrix, similarity = build_similarity(train)
    similarity_matrix = csr_matrix(similarity.sparse.to_coo(), dtype=np.float32)
    movie_positions = {movie_id: position for position, movie_id in enumerate(train_matrix.columns)}
    actual, predicted = [], []
    for row in test.itertuples(index=False):
        prediction = predict_from_matrix(train_matrix, similarity_matrix, row.userId, row.movieId,
                                         movie_positions=movie_positions)
        if prediction is not None:
            actual.append(float(row.rating)); predicted.append(prediction)
    valid = len(actual)
    return {"train_ratings": len(train), "test_ratings": len(test), "valid_predictions": valid,
            "unpredicted": len(test) - valid,
            "rmse": float(np.sqrt(mean_squared_error(actual, predicted))) if valid else None,
            "mae": float(mean_absolute_error(actual, predicted)) if valid else None,
            "split_seed": seed, "test_fraction": test_size}
