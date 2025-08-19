import os
from pathlib import Path
from typing import List, Tuple
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from db.queries import (
    list_boxes, get_box, insert_box, update_box_name,
    get_items, insert_item, replace_items, delete_box_and_children
)
from services.images import best_image_for_name
from services.pricing import local_price_cents
from services.vision import detect_items_json

# NEW: S3 helper
from storage_s3 import upload_fileobj

bp = Blueprint("boxes", __name__)
BASE_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = Path("/tmp")  # only for short-lived analysis

@bp.route("/")
def index():
    boxes = list_boxes()
    return render_template("index.html", boxes=boxes)

@bp.route("/new", methods=["GET", "POST"])
def new_box():
    if request.method == "GET":
        return render_template("new_box.html")

    file = request.files.get("photo")
    if not file or file.filename == "":
        flash("Please choose a photo.")
        return redirect(url_for("boxes.new_box"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        flash("Please upload JPG/PNG/WEBP.")
        return redirect(url_for("boxes.new_box"))

    # --- write to a temp file ONLY for vision (container-friendly) ---
    import tempfile
    with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        file.stream.seek(0)          # ensure start
        tmp.write(file.read())
    # -----------------------------------------------------------------

    # run your AI on the temp path
    try:
        result = detect_items_json(tmp_path)
    except Exception as e:
        result = {"box_name": "Unlabeled Box", "items": [], "notes": f"(analysis failed: {e})"}

    # upload the original image stream to S3 and store its URL in DB
    file.stream.seek(0)  # rewind stream again for S3 upload
    _key, photo_url = upload_fileobj(file.stream, file.filename)

    box_id = insert_box(name=result["box_name"], photo=photo_url, notes=result.get("notes", ""))

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

    # cleanup temp file (best-effort)
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    flash("Analyzed and saved.")
    return redirect(url_for("boxes.box_detail", box_id=box_id))

@bp.route("/box/<int:box_id>", methods=["GET","POST"])
def box_detail(box_id):
    if request.method == "POST":
        # optional new photo -> upload to S3; update DB with URL
        new_photo = request.files.get("new_photo")
        if new_photo and new_photo.filename:
            ext = os.path.splitext(new_photo.filename)[1].lower()
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                new_photo.stream.seek(0)
                _k, new_url = upload_fileobj(new_photo.stream, new_photo.filename)
                from db.connection import get_db
                con = get_db()
                con.execute("UPDATE boxes SET photo=? WHERE id=?", (new_url, box_id))
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

    # photo is now a full URL stored in DB
    photo_url = dict(box).get("photo") or None

    items = get_items(box_id)
    return render_template("box_detail.html", box=box, items=items, photo_url=photo_url)

@bp.route("/box/<int:box_id>/delete", methods=["POST"])
def delete_box(box_id):
    box = get_box(box_id)
    if not box:
        abort(404)
    # delete rows; we don't delete from S3 here (optional)
    delete_box_and_children(box_id)
    flash("Box deleted.")
    return redirect(url_for("boxes.index"))

# REMOVE: the local-file serving route (no longer needed)
# @bp.route("/uploads/<path:filename>")
# def uploaded_file(filename):
#     return send_from_directory(UPLOAD_DIR, filename)
