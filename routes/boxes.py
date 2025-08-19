# routes/boxes.py
from __future__ import annotations

import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, MutableMapping, Any
from uuid import uuid4

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from werkzeug.utils import secure_filename

# DB & services
from db.queries import (
    list_boxes,
    get_box,
    insert_box,
    update_box_name,
    get_items,
    insert_item,
    replace_items,
    delete_box_and_children,
)
from services.images import best_image_for_name
from services.pricing import local_price_cents
from services.vision import detect_items_json

# S3 helpers (no ACLs; presign for display)
from storage_s3 import upload_fileobj, presigned_url

bp = Blueprint("boxes", __name__)

TMP_DIR = Path(tempfile.gettempdir())
TMP_DIR.mkdir(parents=True, exist_ok=True)  # safe if already exists


# ---------- helpers ----------

def _ensure_photo_url_on_box(box_row: MutableMapping[str, Any]) -> None:
    """
    Given a dict-like row with 'photo' holding the S3 key, add a transient
    'photo_url' presigned URL field for templates.
    """
    key = box_row.get("photo")
    box_row["photo_url"] = presigned_url(key) if key else None


# ---------- routes ----------

@bp.route("/")
def index():
    # list_boxes() is assumed to return an iterable of row mappings
    boxes = [dict(b) for b in list_boxes()]
    for b in boxes:
        _ensure_photo_url_on_box(b)
    return render_template("index.html", boxes=boxes)


@bp.route("/new", methods=["GET", "POST"])
def new_box():
    if request.method == "GET":
        return render_template("new_box.html")

    # ---- validate upload ----
    file = request.files.get("photo")
    if not file or not file.filename:
        flash("Please choose a photo.")
        return redirect(url_for("boxes.new_box"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        flash("Please upload JPG/PNG/WEBP.")
        return redirect(url_for("boxes.new_box"))

    # read once into memory
    data = file.read()
    if not data:
        flash("Uploaded file is empty.")
        return redirect(url_for("boxes.new_box"))

    # ---- run vision on a temp file ----
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = detect_items_json(tmp_path)
    except Exception as e:
        # don't block creation if vision fails
        result = {"box_name": "Unlabeled Box", "items": [], "notes": f"(analysis failed: {e})"}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    # ---- upload original image to S3 (no ACLs; bucket enforces owner) ----
    key_name = f"uploads/{uuid4().hex}_{secure_filename(file.filename or 'upload.jpg')}"
    content_type = file.mimetype or "image/jpeg"

    photo_key = upload_fileobj(
        BytesIO(data),
        key_name,
        extra={"ContentType": content_type},  # no ACL
    )

    # ---- persist to DB (store S3 key in 'photo' column) ----
    box_id = insert_box(
        name=(result.get("box_name") or "Unlabeled Box"),
        photo=photo_key,  # store key, not URL
        notes=result.get("notes", ""),
    )

    # persist detected items
    for it in result.get("items", []):
        name = (it.get("name") or "").strip()
        if not name:
            continue
        try:
            conf = float(it.get("confidence") or 0.0)
        except Exception:
            conf = 0.0
        img = best_image_for_name(name)
        price = local_price_cents(name)
        insert_item(
            box_id=box_id,
            name=name,
            confidence=max(0.0, min(1.0, conf)),
            image_url=img,
            price_cents=price,
        )

    flash("Analyzed and saved.")
    return redirect(url_for("boxes.box_detail", box_id=box_id))


@bp.route("/box/<int:box_id>", methods=["GET", "POST"])
def box_detail(box_id: int):
    if request.method == "POST":
        # optional: replace photo
        new_photo = request.files.get("new_photo")
        if new_photo and new_photo.filename:
            ext = os.path.splitext(new_photo.filename)[1].lower()
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                new_key = f"uploads/{uuid4().hex}_{secure_filename(new_photo.filename)}"
                content_type = new_photo.mimetype or "image/jpeg"

                photo_key = upload_fileobj(
                    new_photo.stream,
                    new_key,
                    extra={"ContentType": content_type},  # no ACL
                )

                # Update just the photo key
                from db.connection import get_db
                con = get_db()
                con.execute("UPDATE boxes SET photo=? WHERE id=?", (photo_key, box_id))
                con.commit()
                con.close()
                flash("Photo updated.")

        # update name + items
        name = (request.form.get("name") or "Unnamed Box").strip()
        update_box_name(box_id, name)

        pairs: List[Tuple[str, float, str, int | None]] = []
        for k, v in request.form.items():
            if k.startswith("items[") and k.endswith("].name"):
                idx = k.split("[", 1)[1].split("]")[0]
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

    # GET branch
    row = get_box(box_id)
    if not row:
        abort(404)

    box = dict(row)
    _ensure_photo_url_on_box(box)
    items = get_items(box_id)

    return render_template("box_detail.html", box=box, items=items, photo_url=box["photo_url"])


@bp.route("/box/<int:box_id>/delete", methods=["POST"])
def delete_box(box_id: int):
    row = get_box(box_id)
    if not row:
        abort(404)
    delete_box_and_children(box_id)
    flash("Box deleted.")
    return redirect(url_for("boxes.index"))
