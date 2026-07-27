import hashlib
import io
import json
import os
import shutil
from datetime import datetime

from flask import Flask, request, render_template, send_file, abort, redirect, url_for
from PIL import Image, ImageOps

app = Flask(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
THUMB_SIZE = (640, 640)
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".thumb_cache")
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]
STATE_FILENAME = ".organizer_state.json"
LAST_FOLDER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_folder.txt")

os.makedirs(CACHE_DIR, exist_ok=True)


def load_last_folder():
    if os.path.isfile(LAST_FOLDER_FILE):
        try:
            with open(LAST_FOLDER_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""


def save_last_folder(folder):
    try:
        with open(LAST_FOLDER_FILE, "w", encoding="utf-8") as f:
            f.write(folder)
    except Exception:
        pass


def state_file_path(folder):
    return os.path.join(folder, STATE_FILENAME)


def load_keep_state(folder):
    """作業中のチェック状態（残す写真名の集合）を読み込む"""
    path = state_file_path(folder)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("keep", []))
        except Exception:
            return set()
    return set()


def save_keep_state(folder, keep_names):
    path = state_file_path(folder)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"keep": sorted(keep_names)}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def delete_keep_state(folder):
    path = state_file_path(folder)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except Exception:
            pass


def list_images(folder):
    """指定フォルダ直下の画像ファイル名一覧（ソート済み）を返す"""
    names = []
    with os.scandir(folder) as it:
        for entry in it:
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in IMAGE_EXTS:
                    names.append(entry.name)
    names.sort()
    return names


def get_photo_datetime(path):
    """Exif撮影日時を優先し、無ければファイル更新日時を使う"""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            exif_ifd = exif.get_ifd(0x8769) if exif else {}
            dt_str = exif_ifd.get(36867) or exif_ifd.get(36868) or exif.get(306)
            if dt_str:
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(os.path.getmtime(path))


def group_by_day(folder):
    """フォルダ内の画像をExif撮影日ごとにグループ化する"""
    names = list_images(folder)
    items = []
    for name in names:
        path = os.path.join(folder, name)
        dt = get_photo_datetime(path)
        items.append((name, dt))
    items.sort(key=lambda x: x[1])

    groups = {}
    for name, dt in items:
        day = dt.date()
        groups.setdefault(day, []).append((name, dt))

    result = []
    for day in sorted(groups.keys()):
        photos = [
            {"name": name, "time": dt.strftime("%H:%M:%S")}
            for name, dt in groups[day]
        ]
        label = f"{day.strftime('%Y-%m-%d')} ({WEEKDAY_JP[day.weekday()]})"
        result.append({"label": label, "count": len(photos), "photos": photos})
    return result, len(names)


def safe_path(folder, filename):
    """folder配下のfilenameであることを保証した絶対パスを返す"""
    folder_real = os.path.realpath(folder)
    target = os.path.realpath(os.path.join(folder, filename))
    if os.path.dirname(target) != folder_real:
        abort(400)
    return target


def thumb_cache_path(path):
    mtime = os.path.getmtime(path)
    key = hashlib.md5(f"{path}:{mtime}:{THUMB_SIZE}".encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, key + ".jpg")


@app.route("/")
def index():
    folder = request.args.get("folder", "").strip()
    if not folder:
        folder = load_last_folder()
    groups = []
    total = 0
    error = None
    keep_set = set()
    if folder:
        if os.path.isdir(folder):
            try:
                groups, total = group_by_day(folder)
                keep_set = load_keep_state(folder)
                if total == 0:
                    error = "このフォルダに画像ファイルが見つかりませんでした。"
                save_last_folder(folder)
            except Exception as e:
                error = f"読み込み中にエラーが発生しました: {e}"
        else:
            error = "指定されたフォルダが見つかりません。"
    return render_template(
        "index.html", folder=folder, groups=groups, total=total, error=error, keep_set=keep_set
    )


@app.route("/save_state", methods=["POST"])
def save_state():
    data = request.get_json(silent=True) or {}
    folder = (data.get("folder") or "").strip()
    keep = data.get("keep") or []
    if not folder or not os.path.isdir(folder):
        abort(400)
    save_keep_state(folder, keep)
    return {"ok": True}


@app.route("/thumb")
def thumb():
    folder = request.args.get("folder", "")
    filename = request.args.get("file", "")
    if not folder or not filename:
        abort(400)
    path = safe_path(folder, filename)
    if not os.path.isfile(path):
        abort(404)

    cache_path = thumb_cache_path(path)
    if not os.path.isfile(cache_path):
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMB_SIZE)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(cache_path, "JPEG", quality=80)
    return send_file(cache_path, mimetype="image/jpeg")


@app.route("/photo")
def photo():
    folder = request.args.get("folder", "")
    filename = request.args.get("file", "")
    if not folder or not filename:
        abort(400)
    path = safe_path(folder, filename)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)


@app.route("/execute", methods=["POST"])
def execute():
    folder = request.form.get("folder", "").strip()
    if not folder or not os.path.isdir(folder):
        abort(400)

    all_names = set(list_images(folder))
    keep_names = set(request.form.getlist("keep"))
    delete_names = sorted(all_names - keep_names)

    delete_dir = os.path.join(folder, "delete")
    moved = []
    if delete_names:
        os.makedirs(delete_dir, exist_ok=True)
        for name in delete_names:
            src = os.path.join(folder, name)
            dst = os.path.join(delete_dir, name)
            if os.path.exists(dst):
                base, ext = os.path.splitext(name)
                i = 1
                while os.path.exists(dst):
                    dst = os.path.join(delete_dir, f"{base}_{i}{ext}")
                    i += 1
            shutil.move(src, dst)
            moved.append(name)

    delete_keep_state(folder)

    return render_template(
        "done.html", folder=folder, moved=moved, kept_count=len(all_names) - len(moved)
    )


if __name__ == "__main__":
    app.run(debug=True)
