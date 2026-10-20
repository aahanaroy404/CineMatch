"""Item-based collaborative filtering using cosine movie similarity."""
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse import issparse
from sklearn.metrics.pairwise import cosine_similarity


def build_similarity(ratings: pd.DataFrame):
    """Build a movie-by-movie cosine matrix from observed ratings only.

    The matrix stays sparse: an unobserved user/movie cell has no stored
    rating and contributes no product to the cosine numerator. Column norms
    use only each movie's observed ratings, so unknowns are not dislikes.
    """
    matrix = ratings.pivot_table(index="userId", columns="movieId", values="rating", aggfunc="mean")
    observed = csr_matrix(matrix.fillna(0.0).to_numpy(dtype=np.float32).T)
    similarities = cosine_similarity(observed, dense_output=False)
    return matrix, pd.DataFrame.sparse.from_spmatrix(
        similarities, index=matrix.columns, columns=matrix.columns
    )


def recommend(ratings, user_ratings, limit=10, minimum_ratings=2):
    matrix, similarity = build_similarity(ratings)
    rated = {int(k): float(v) for k, v in user_ratings.items() if int(k) in similarity.index}
    if len(rated) < minimum_ratings:
        return [], {"status": "insufficient_ratings", "rated_count": len(rated),
                    "message": f"Rate at least {minimum_ratings} movies that appear in the dataset to get personalized recommendations."}
    scored = []
    for candidate in similarity.columns:
        if int(candidate) in rated:
            continue
        neighbors = [(movie_id, score) for movie_id, score in rated.items() if similarity.at[candidate, movie_id] > 0]
        if not neighbors:
            continue
        # Weighted deviations from user's average; similarity magnitude
        # normalizes, while the sign keeps negatively related items distinct.
        weights = np.array([float(sim) for _, sim in neighbors])
        if np.abs(weights).sum() < 1e-9:
            continue
        user_mean = float(np.mean(list(rated.values())))
        deviations = np.array([rated[mid] - user_mean for mid, _ in neighbors])
        prediction = float(np.clip(user_mean + np.dot(weights, deviations) / np.abs(weights).sum(), 0.5, 5.0))
        support = sorted(neighbors, key=lambda pair: pair[1], reverse=True)
        scored.append((int(candidate), prediction, support[:2]))
    scored.sort(key=lambda row: (-row[1], row[0]))
    return scored[:limit], {"status": "ok", "rated_count": len(rated)}


def predict_from_matrix(train_matrix, similarity, user_id, movie_id, min_neighbors=1, movie_positions=None):
    """Predict one held-out rating using only training observations."""
    if user_id not in train_matrix.index:
        return None
    if issparse(similarity):
        if movie_positions is None or movie_id not in movie_positions:
            return None
    elif movie_id not in similarity.index:
        return None
    observed = train_matrix.loc[user_id].dropna()
    observed = observed[observed.index != movie_id]
    if observed.empty:
        return None
    if issparse(similarity):
        if movie_positions is None:
            raise ValueError("movie_positions is required for sparse similarity lookup")
        target_pos = movie_positions.get(movie_id)
        neighbor_positions = np.array([movie_positions[item_id] for item_id in observed.index], dtype=np.int32)
        if target_pos is None:
            return None
        sims = similarity.getrow(target_pos)[:, neighbor_positions].toarray().ravel()
    else:
        sims = np.array([float(similarity.at[movie_id, item_id]) for item_id in observed.index])
    sims = np.clip(sims, 0, None)
    valid_mask = sims > 0
    valid_ids = observed.index[valid_mask]
    valid_sims = sims[valid_mask]
    if len(valid_ids) < min_neighbors or valid_sims.sum() == 0:
        return None
    baseline = float(observed.mean())
    deviations = observed.loc[valid_ids].to_numpy(dtype=float) - baseline
    return float(np.clip(baseline + np.dot(valid_sims, deviations) / valid_sims.sum(), 0.5, 5.0))
