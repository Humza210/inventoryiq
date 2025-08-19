# routes/search.py
from flask import Blueprint, render_template, request
from db.queries import search_items

bp = Blueprint("search", __name__, url_prefix="/search")

@bp.route("/", methods=["GET", "POST"])
def search():
    q = (request.values.get("q") or "").strip()
    results = search_items(q)

    # JSON-safe copy
    results_json = [dict(r) for r in (results or [])]

    return render_template(
        "search.html",
        q=q,
        results=results,          # SSR fallback
        results_json=results_json # for JS bootstrap
    )
