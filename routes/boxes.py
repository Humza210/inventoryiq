import os
from pathlib import Path
from typing import List, Tuple
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_from_directory

from db.queries import (
    list_boxes, get_box, insert_box, update_box_name,
    get_items, insert_item, replace_items, delete_box_and_children
)
from services.images import best_image_for_name
from services.pricing import local_price_cents
from services.vision import detect_items_json

bp = Blueprint("boxes", __name__)
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "uploads"

@bp.route("/")
def index():
    boxes = list_boxes()
    return render_template("index.html", boxes=boxes)

@bp.route("/new", methods=["GET", "POST"])
def new_box():
    if request.method == "GET":
        # ensure uploads dir exists
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return render_template("new_box.html")

    # --------- POST: same behavior you had (just small hardening) ----------
    file = request.files.get("photo")
    if not file or file.filename == "":
        flash("Please choose a photo.")
        return redirect(url_for("boxes.new_box"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        flash("Please upload JPG/PNG/WEBP.")
        return redirect(url_for("boxes.new_box"))

    # robust unique name
    import time, uuid
    fname = f"{int(time.time()*1e9)}-{uuid.uuid4().hex}{ext}"
    fpath = UPLOAD_DIR / fname
    file.save(fpath)

    try:
        result = detect_items_json(str(fpath))
    except Exception as e:
        result = {"box_name": "Unlabeled Box", "items": [], "notes": f"(analysis failed: {e})"}

    box_id = insert_box(name=result["box_name"], photo=fname, notes=result.get("notes", ""))

    for it in result["items"]:
        img = best_image_for_name(it["name"])
        price = local_price_cents(it["name"])
        insert_item(
            box_id=box_id,
            name=it["name"],
            confidence=it["confidence"],
            image_url=img,
            price_cents=price
        )

    flash("Analyzed and saved.")
    return redirect(url_for("boxes.box_detail", box_id=box_id))

@bp.route("/box/<int:box_id>", methods=["GET","POST"])
def box_detail(box_id):
    if request.method == "POST":
        new_photo = request.files.get("new_photo")
        if new_photo and new_photo.filename:
            ext = os.path.splitext(new_photo.filename)[1].lower()
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                fname = f"{int(Path().stat().st_mtime_ns)}{ext}"
                new_photo.save(UPLOAD_DIR / fname)
                from db.connection import get_db
                con = get_db()
                con.execute("UPDATE boxes SET photo=? WHERE id=?", (fname, box_id))
                con.commit()
                con.close()
                flash("Photo updated.")

        name = (request.form.get("name") or "Unnamed Box").strip()
        update_box_name(box_id, name)

        # collect edits
        pairs: List[Tuple[str, float, str, int | None]] = []
        for k, v in request.form.items():
            if k.startswith("items[") and k.endswith("].name"):
                idx = k.split("[",1)[1].split("]")[0]
                n = (v or "").strip()
                try:
                    c = float(request.form.get(f"items[{idx}].confidence", "0") or 0)
                except Exception:
                    c = 0.0
                img = best_image_for_name(n) if n else ""
                price = local_price_cents(n) if n else None
                if n:
                    pairs.append((n, max(0.0, min(1.0, c)), img, price))

        if pairs:
            replace_items(box_id, pairs)

        return redirect(url_for("boxes.box_detail", box_id=box_id))

    box = get_box(box_id)
    if not box:
        abort(404)
    photo_val = dict(box).get("photo")
    photo_url = url_for("boxes.uploaded_file", filename=photo_val) if photo_val else None
    items = get_items(box_id)
    return render_template("box_detail.html", box=box, items=items, photo_url=photo_url)

@bp.route("/box/<int:box_id>/delete", methods=["POST"])
def delete_box(box_id):
    box = get_box(box_id)
    if not box:
        abort(404)
    photo = delete_box_and_children(box_id)
    if photo:
        from pathlib import Path
        UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
        try:
            (UPLOAD_DIR / photo).unlink(missing_ok=True)
        except Exception:
            pass
    flash("Box deleted.")
    return redirect(url_for("boxes.index"))


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)
