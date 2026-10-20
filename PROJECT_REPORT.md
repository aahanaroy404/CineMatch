# CineMatch: Movie Recommendation with Collaborative Filtering

## Abstract

CineMatch is a movie discovery mini-project built with React, FastAPI, and SQLite. It stores account-specific explicit ratings and applies item-based collaborative filtering with cosine similarity to rank unseen movies. Users with little rating history receive transparently labeled popularity-based suggestions derived from MovieLens. A deterministic holdout pipeline measures prediction error. The application also demonstrates account security, profile persistence, and server-protected aggregate administration.

## Introduction and problem statement

Large movie catalogs make it difficult for viewers to choose a film. A recommender system uses preference information to narrow the catalog. The project demonstrates how historical ratings from multiple viewers can identify relationships between movies and support estimates for a user's unrated titles.

## Objectives

- Store explicit user ratings and represent dataset feedback as a sparse user-item matrix.
- Calculate sparse item cosine similarity from observed rating vectors.
- Rank unseen titles using similarity-weighted prediction scores.
- Persist separate profiles and ratings securely in SQLite.
- Handle cold-start with clearly labeled dataset-based popular suggestions.
- Evaluate prediction accuracy on held-out ratings using RMSE and MAE.
- Provide an aggregate-only admin dashboard protected by backend role checks.

## Dataset

The application uses MovieLens Latest Small from GroupLens. It reads `movies.csv` (movie IDs, titles, genres) and `ratings.csv` (user IDs, movie IDs, explicit 0.5–5 star values, timestamps). The current copy includes these two dataset files under `data/ml-latest-small/`; data is excluded from Git. The catalog computes average rating and rating count from the loaded MovieLens rows. Popular suggestions require at least 25 ratings and are sorted by average rating, then count. GroupLens dataset attribution and use conditions should be followed in academic submissions.

## Methodology

Let `R` be the user-by-movie matrix. A present cell is a MovieLens rating; a blank cell means unknown and is not stored as a zero rating. The implementation uses a sparse representation, where unknown cells contribute no product to the cosine numerator or observed column norms. Cosine similarity is:

`sim(i,j) = (vᵢ · vⱼ) / (||vᵢ|| ||vⱼ||)`

For user `u`, the baseline `μᵤ` is the mean of the movies that user rated in the app. An unseen movie's estimate is the weighted average of the user's rating deviations on similar movies, normalized by absolute similarity magnitude:

`r̂(u,i) = clip(μᵤ + Σⱼ sim(i,j)(r(u,j) − μᵤ) / Σⱼ |sim(i,j)|, 0.5, 5)`

Only positive movie similarities are used to select neighbors in online recommendations. Movies already rated by the user are excluded. The implementation requires two ratings for personalized recommendations. With no ratings it shows only popularity suggestions; with one rating it explains that personalization needs more input and offers the same clearly labeled popular suggestions.

## System architecture

The React/Vite single-page frontend communicates with a local FastAPI backend. SQLite stores user accounts, password hashes, revocable sessions, the current ratings for each user/movie pair, and aggregate recommendation counts. The backend loads MovieLens CSVs for catalog and model behavior. An HttpOnly cookie carries a random opaque session token; only its SHA-256 hash is stored in the database. Role and user identity come from that validated server-side session.

## Implementation details

- `backend/auth.py`: PBKDF2-HMAC-SHA256 password hashing with per-password random salts; opaque 12-hour sessions; logout invalidation; server-side admin dependency.
- `backend/database.py`: SQLite schema for accounts, sessions, user ratings, and recommendation event counts.
- `backend/bootstrap_admin.py`: interactive one-time first-admin command; prompts for a long password without echo; stops once any administrator exists.
- `backend/recommender.py`: item similarity and weighted deviation prediction.
- `backend/main.py`: registration/login/logout, movie catalog, per-user profile/ratings, evaluation, and aggregate-only admin API.
- `frontend/src/App.jsx`: authentication screen, discovery/search, rating, Profile with stacked Your Rated Movies and For You sections, evaluation, approachable algorithm explanation, and Admin Dashboard.

Recommendation totals count movie suggestions actually returned in each profile refresh response, including popular suggestions. Empty results add zero. Computed candidate scores that are not returned do not add to the count. Admin statistics reveal aggregate counts only.

## Evaluation methodology and results

The evaluation uses a seeded 80/20 split (`random_state=42`). It constructs movie similarities using training ratings only. For each held-out row, it predicts only when the user's training ratings include a positively similar movie. Unpredictable rows are excluded from the metric calculation and reported separately. RMSE is the square root of average squared prediction error; MAE is average absolute error over the same valid predictions. On the included MovieLens Latest Small ratings file, the run produced **RMSE 0.9202** and **MAE 0.7103** over **19,351 valid predictions**. The split contained **80,668 training ratings**, **20,168 test ratings**, and **817 unpredicted test cases**. These values are computed from the data, not hardcoded.

## Limitations

Sparse rating overlap means some movie pairs have no similarity evidence and some test ratings cannot be predicted. New users initially receive popularity-based suggestions; newly added movies have no collaborative history. Popularity sorting can reflect dataset bias. SQLite and local cookie sessions suit a local educational demo; this app is not a public multi-tenant identity service. The admin dashboard intentionally displays only aggregate totals.

## Conclusion and future scope

CineMatch demonstrates how explicit ratings produce item relationships and personalized ranked suggestions, while handling unknown ratings and new-user cold-start transparently. It adds persistent user accounts and backend-enforced admin access without changing the core collaborative filtering approach. Future work could add coverage-aware evaluation, stronger deployment controls, and richer profile preference summaries without obscuring how recommendations are made.

## References

1. F. M. Harper and J. A. Konstan, “The MovieLens Datasets: History and Context,” *ACM Transactions on Interactive Intelligent Systems*, 5(4), 2015. <https://doi.org/10.1145/2827872>
2. GroupLens Research, MovieLens Latest Small. <https://grouplens.org/datasets/movielens/latest/>
3. scikit-learn, cosine similarity documentation. <https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html>

## 8-slide presentation outline

1. **Motivation** — choosing from a large movie collection.
2. **Objectives and user flow** — register, rate, discover, and get picks.
3. **MovieLens data** — explicit ratings, titles, genres, and missing values.
4. **Recommendation model** — pairwise cosine similarity and weighted rating prediction.
5. **Cold-start behavior** — computed popular picks until enough ratings exist.
6. **Application architecture and security** — React, FastAPI, SQLite, hashed passwords, sessions.
7. **Evaluation and admin totals** — real holdout metrics and aggregate counts.
8. **Limitations and conclusion** — sparsity, cold-start, and future work.
