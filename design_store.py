import base64
import copy
import io
import json
import os
import uuid
import zipfile

import pymupdf as fitz

DESIGNS_DIR = "designs"

PORTRAIT_WIDTH = 595.5
PORTRAIT_HEIGHT = 842.25

# Jede Schrift, die im Canvas-Editor und im PDF zur Verfügung steht.
# cssFamily/weight/style steuern die Browser-Vorschau, der Dict-Key selbst
# ist immer der reportlab-Fontname für den PDF-Export.
FONT_DEFINITIONS = {
    "GreatVibes": {"label": "GreatVibes (Handschrift)", "cssFamily": "GreatVibesWeb", "embed": True},
    "Times-Roman": {"label": "Times Roman", "cssFamily": "Times New Roman", "weight": "normal", "style": "normal"},
    "Times-Bold": {"label": "Times Bold", "cssFamily": "Times New Roman", "weight": "bold", "style": "normal"},
    "Times-Italic": {"label": "Times Italic", "cssFamily": "Times New Roman", "weight": "normal", "style": "italic"},
    "Times-BoldItalic": {"label": "Times Bold Italic", "cssFamily": "Times New Roman", "weight": "bold", "style": "italic"},
    "Helvetica": {"label": "Helvetica", "cssFamily": "Arial", "weight": "normal", "style": "normal"},
    "Helvetica-Bold": {"label": "Helvetica Bold", "cssFamily": "Arial", "weight": "bold", "style": "normal"},
    "Helvetica-Oblique": {"label": "Helvetica Oblique", "cssFamily": "Arial", "weight": "normal", "style": "italic"},
    "Helvetica-BoldOblique": {"label": "Helvetica Bold Oblique", "cssFamily": "Arial", "weight": "bold", "style": "italic"},
}

FONT_CHOICES = list(FONT_DEFINITIONS.keys())

GREATVIBES_FONT_PATH = os.path.join("fonts", "GreatVibes-Regular.ttf")


def build_font_faces():
    """Baut die Font-Definitionen für den Canvas-Editor, inkl. eingebetteter
    Web-Font-Daten (z. B. GreatVibes) als data:-URL."""
    faces = {}

    for font_id, info in FONT_DEFINITIONS.items():
        face = dict(info)

        if info.get("embed") and os.path.exists(GREATVIBES_FONT_PATH):
            with open(GREATVIBES_FONT_PATH, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
            face["dataUrl"] = f"data:font/ttf;base64,{encoded}"

        faces[font_id] = face

    return faces


def default_page(orientation="portrait"):
    if orientation == "landscape":
        return {"width": PORTRAIT_HEIGHT, "height": PORTRAIT_WIDTH, "orientation": "landscape"}

    return {"width": PORTRAIT_WIDTH, "height": PORTRAIT_HEIGHT, "orientation": "portrait"}


def _text_layer(content, x, y, width, height, font, size, color="#000000", align="left"):
    return {
        "id": str(uuid.uuid4()), "type": "text", "content": content,
        "x": x, "y": y, "width": width, "height": height, "angle": 0,
        "font": font, "size": size, "color": color, "align": align
    }


def default_urkunde_layers():
    """Startlayout einer neuen Urkunde (frei verschiebbar) - orientiert sich
    grob am bisherigen festen Layout, dient nur als Ausgangspunkt."""
    return [
        _text_layer("{name}", 100, 300, 395, 70, "GreatVibes", 48, "#161616", "center"),
        _text_layer("zum", 250, 385, 95, 30, "Times-Roman", 20, "#000000", "center"),
        _text_layer("{rank}. PLATZ", 175, 420, 245, 42, "Times-Roman", 31, "#000000", "center"),
        _text_layer("in {event}", 175, 480, 180, 32, "Times-Roman", 22, "#000000", "left"),
        {
            "id": str(uuid.uuid4()), "type": "event_logo",
            "x": 365, "y": 478, "width": 30, "height": 30, "angle": 0, "color": None
        },
        _text_layer("bei den {competition}", 100, 530, 395, 32, "Times-Roman", 21, "#000000", "center"),
        _text_layer("{result_label}", 100, 575, 395, 28, "Times-Roman", 20, "#000000", "center"),
        _text_layer("{result}", 100, 615, 395, 28, "Times-Roman", 20, "#000000", "center"),
    ]


def default_urkunde_design():
    return {
        "page": default_page(),
        "background": {"type": "none"},
        "layers": default_urkunde_layers()
    }


DEFAULT_NAMENSSCHILD_DESIGN = {
    "logo_path": None,
    "logo_scale": 1.0
}


def _competition_dir(competition_id):
    path = os.path.join(DESIGNS_DIR, competition_id)
    os.makedirs(path, exist_ok=True)
    return path


def get_urkunde_design(competition_id):
    """Lädt den gespeicherten Urkunden-Entwurf einer Competition, oder das
    Standard-Layout, falls noch keiner gespeichert wurde."""
    path = os.path.join(_competition_dir(competition_id), "urkunde.json")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    return default_urkunde_design()


def save_urkunde_design(competition_id, design):
    path = os.path.join(_competition_dir(competition_id), "urkunde.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(design, f, indent=2, ensure_ascii=False)


def save_background_bytes(competition_id, image_bytes, ext=".png"):
    """Speichert Hintergrundbild-Bytes (z. B. aus dem Arbeits-Entwurf) dauerhaft
    und gibt den lokalen Pfad zurück."""
    path = os.path.join(_competition_dir(competition_id), f"urkunde_background{ext}")

    with open(path, "wb") as f:
        f.write(image_bytes)

    return path


def data_url_to_bytes(data_url):
    """Zerlegt eine 'data:image/png;base64,....'-URL in (Bytes, Dateiendung)."""
    header, encoded = data_url.split(",", 1)
    ext = ".png"

    if "image/jpeg" in header or "image/jpg" in header:
        ext = ".jpg"
    elif "image/png" in header:
        ext = ".png"
    elif "image/gif" in header:
        ext = ".gif"
    elif "image/webp" in header:
        ext = ".webp"

    return base64.b64decode(encoded), ext


def file_to_data_url(path):
    """Liest eine Bilddatei ein und gibt sie als data:-URL zurück (für die
    Anzeige im Canvas-Editor)."""
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    mime = "jpeg" if ext == "jpg" else ext

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    return f"data:image/{mime};base64,{encoded}"


def save_layer_image(competition_id, layer_id, data_url):
    """Speichert die Bild-Bytes eines Bild-Layers (data:-URL aus dem
    Canvas-Editor) dauerhaft und gibt den Dateipfad zurück."""
    image_bytes, ext = data_url_to_bytes(data_url)
    path = os.path.join(_competition_dir(competition_id), f"layer_{layer_id}{ext}")

    with open(path, "wb") as f:
        f.write(image_bytes)

    return path


def prepare_layers_for_canvas(competition_id, layers):
    """Reichert gespeicherte Bild-Layer (die nur einen Dateipfad enthalten)
    wieder mit einer data:-URL an, damit der Canvas-Editor sie anzeigen kann."""
    prepared = []

    for layer in layers:
        layer = dict(layer)

        if layer.get("type") == "image" and layer.get("path") and not layer.get("src"):
            if os.path.exists(layer["path"]):
                layer["src"] = file_to_data_url(layer["path"])

        prepared.append(layer)

    return prepared


def persist_layer_images(competition_id, layers):
    """Speichert alle neuen (per data:-URL übergebenen) Bild-Layer dauerhaft
    auf die Festplatte und ersetzt 'src' durch den gespeicherten Pfad."""
    persisted = []

    for layer in layers:
        layer = dict(layer)

        if layer.get("type") == "image" and layer.get("src", "").startswith("data:"):
            layer["path"] = save_layer_image(competition_id, layer["id"], layer["src"])
            layer.pop("src", None)

        persisted.append(layer)

    return persisted


def export_design_to_zip(design):
    """Packt einen Design-Entwurf (design.json + referenzierte Bilder, egal ob
    schon gespeichert ('path') oder noch unsaved im Speicher ('data'/'src'))
    als ZIP-Bytes zum Herunterladen. Kann anschließend über parse_design_zip()
    in eine andere Competition importiert werden."""
    design_copy = copy.deepcopy(design)
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        background = design_copy.get("background") or {}

        if background.get("type") == "image":
            if background.get("path") and os.path.exists(background["path"]):
                ext = os.path.splitext(background["path"])[1] or ".png"
                arcname = f"assets/background{ext}"
                zf.write(background["path"], arcname=arcname)
                background = {"type": "image", "path": arcname}
            elif background.get("data"):
                arcname = f"assets/background{background.get('ext', '.png')}"
                zf.writestr(arcname, background["data"])
                background = {"type": "image", "path": arcname}

        design_copy["background"] = background

        new_layers = []

        for layer in design_copy.get("layers", []):
            layer = dict(layer)

            if layer.get("type") == "image":
                if layer.get("path") and os.path.exists(layer["path"]):
                    ext = os.path.splitext(layer["path"])[1] or ".png"
                    arcname = f"assets/{layer['id']}{ext}"
                    zf.write(layer["path"], arcname=arcname)
                    layer["path"] = arcname
                    layer.pop("src", None)
                elif str(layer.get("src", "")).startswith("data:"):
                    image_bytes, ext = data_url_to_bytes(layer["src"])
                    arcname = f"assets/{layer['id']}{ext}"
                    zf.writestr(arcname, image_bytes)
                    layer["path"] = arcname
                    layer.pop("src", None)

            new_layers.append(layer)

        design_copy["layers"] = new_layers

        zf.writestr("design.json", json.dumps(design_copy, indent=2, ensure_ascii=False))

    buffer.seek(0)
    return buffer.read()


def parse_design_zip(zip_bytes):
    """Liest eine per export_design_to_zip() erzeugte ZIP-Datei und gibt ein
    Design-Dict zurück, bei dem Bilder als In-Memory-Daten ('data'/'src')
    statt Dateipfaden vorliegen - direkt als Arbeits-Entwurf nutzbar, ohne
    vorher etwas fest zu speichern (Bearbeiten vor dem Speichern bleibt möglich)."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        design = json.loads(zf.read("design.json").decode("utf-8"))

        assets = {
            os.path.basename(name): zf.read(name)
            for name in zf.namelist()
            if name.startswith("assets/") and not name.endswith("/")
        }

    background = design.get("background") or {}

    if background.get("path"):
        asset_bytes = assets.get(os.path.basename(background["path"]))
        ext = os.path.splitext(background["path"])[1].lower() or ".png"
        background = {"type": "image", "data": asset_bytes, "ext": ext} if asset_bytes else {"type": "none"}

    design["background"] = background

    new_layers = []

    for layer in design.get("layers", []):
        layer = dict(layer)

        if layer.get("type") == "image" and layer.get("path"):
            asset_bytes = assets.get(os.path.basename(layer["path"]))

            if asset_bytes:
                ext = os.path.splitext(layer["path"])[1].lower().lstrip(".") or "png"
                mime = "jpeg" if ext == "jpg" else ext
                layer["src"] = f"data:image/{mime};base64," + base64.b64encode(asset_bytes).decode("ascii")

            layer.pop("path", None)

        new_layers.append(layer)

    design["layers"] = new_layers

    return design


def get_namensschild_design(competition_id):
    """Lädt den gespeicherten Namensschild-Entwurf (aktuell nur das
    Competition-Logo) einer Competition, oder die Standardwerte."""
    path = os.path.join(_competition_dir(competition_id), "namensschild.json")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    return copy.deepcopy(DEFAULT_NAMENSSCHILD_DESIGN)


def save_namensschild_design(competition_id, design):
    path = os.path.join(_competition_dir(competition_id), "namensschild.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(design, f, indent=2, ensure_ascii=False)


def save_namensschild_logo(competition_id, uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".png"
    path = os.path.join(_competition_dir(competition_id), f"namensschild_logo{ext}")

    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return path


def render_preview_png(pdf_bytes, dpi=120):
    """Rendert die erste Seite eines PDFs (als Bytes) als PNG-Bytes für die
    Live-Vorschau in der UI."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        page = doc.load_page(0)
        zoom = dpi / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()


def pdf_first_page_to_png(pdf_bytes, dpi=300):
    """Rastert die erste Seite eines hochgeladenen PDFs (z. B. als Urkunden-
    Hintergrund) in hoher Auflösung zu PNG-Bytes."""
    return render_preview_png(pdf_bytes, dpi=dpi)
