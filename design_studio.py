import base64
import copy
import os
from io import BytesIO

import streamlit as st
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import landscape, A4

import design_store
import design_canvas
import wca_common
import urkunde_generator


SAMPLE_URKUNDE_CONTEXT = {
    "name": "Max Mustermann",
    "rank": 1,
    "event": "3x3",
    "event_id": "333",
    "competition": "Beispiel Competition 2026",
    "result": "8.42"
}


def _mime_for_ext(ext):
    ext = (ext or ".png").lower().lstrip(".")
    return "jpeg" if ext in ("jpg", "jpeg") else ext


def _background_data_url(background):
    if not background or background.get("type") != "image":
        return None

    if background.get("data"):
        mime = _mime_for_ext(background.get("ext"))
        return f"data:image/{mime};base64," + base64.b64encode(background["data"]).decode("ascii")

    if background.get("path") and os.path.exists(background["path"]):
        return design_store.file_to_data_url(background["path"])

    return None


def render_urkunde_design_studio(competition_id):
    st.header("🎨 Urkunden-Design")

    st.write(
        "Gestalte die Urkunde frei wie auf einer Leinwand: Text- und Bild-"
        "Elemente per Drag & Drop platzieren, skalieren und drehen."
    )

    working_key = f"urkunde_working_design__{competition_id}"
    revision_key = f"urkunde_design_revision__{competition_id}"
    orientation_key = f"urkunde_orientation__{competition_id}"

    if working_key not in st.session_state:
        st.session_state[working_key] = design_store.get_urkunde_design(competition_id)
        st.session_state[revision_key] = 0

    working_design = st.session_state[working_key]

    # --------------------------------------------------------------
    # Vorlage importieren
    # --------------------------------------------------------------
    with st.expander("📂 Vorlage importieren (von einer anderen Competition)"):
        imported_zip = st.file_uploader(
            "Heruntergeladene .zip-Vorlage hochladen",
            type=["zip"],
            key=f"urkunde_import_zip__{competition_id}"
        )

        if imported_zip is not None and st.button("Importieren", key=f"urkunde_do_import__{competition_id}"):
            imported_design = design_store.parse_design_zip(imported_zip.getvalue())
            st.session_state[working_key] = imported_design
            st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1
            st.session_state.pop(orientation_key, None)
            st.success("Vorlage importiert. Bitte prüfen, ggf. anpassen und dann speichern.")
            st.rerun()

    # --------------------------------------------------------------
    # Seitenformat
    # --------------------------------------------------------------
    current_orientation = (working_design.get("page") or {}).get("orientation", "portrait")

    orientation_label = st.radio(
        "Seitenformat",
        ["Hochformat", "Querformat"],
        index=0 if current_orientation == "portrait" else 1,
        horizontal=True,
        key=orientation_key
    )

    new_orientation = "portrait" if orientation_label == "Hochformat" else "landscape"

    if new_orientation != current_orientation:
        working_design["page"] = design_store.default_page(new_orientation)
        st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1

    # --------------------------------------------------------------
    # Hintergrund
    # --------------------------------------------------------------
    st.subheader("Hintergrund")

    uploaded_background = st.file_uploader(
        "Hintergrundbild hochladen (PNG/JPG oder PDF, volle Seite)",
        type=["png", "jpg", "jpeg", "pdf"],
        key=f"urkunde_bg_upload__{competition_id}"
    )

    bg_col1, bg_col2 = st.columns(2)

    if bg_col1.button(
        "Hintergrund übernehmen", use_container_width=True,
        disabled=uploaded_background is None, key=f"urkunde_bg_apply__{competition_id}"
    ):
        background_bytes = uploaded_background.getvalue()
        background_ext = os.path.splitext(uploaded_background.name)[1].lower()

        if background_ext == ".pdf":
            with st.spinner("PDF wird als Hintergrund gerendert..."):
                background_bytes = design_store.pdf_first_page_to_png(background_bytes)
            background_ext = ".png"

        working_design["background"] = {"type": "image", "data": background_bytes, "ext": background_ext}
        st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1

    if bg_col2.button("Hintergrund entfernen", use_container_width=True, key=f"urkunde_bg_remove__{competition_id}"):
        working_design["background"] = {"type": "none"}
        st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1

    # --------------------------------------------------------------
    # Canvas-Editor
    # --------------------------------------------------------------
    st.subheader("Editor")
    st.caption(
        "Ziehen zum Verschieben, Ecken zum Skalieren, oberer Griff zum Drehen. "
        "Doppelklick auf Text zum Bearbeiten. Platzhalter wie {name}, {rank}, "
        "{event}, {competition}, {result}, {result_label} bleiben beim Erstellen dynamisch."
    )

    page = working_design.get("page") or design_store.default_page()

    canvas_result = design_canvas.design_canvas(
        page_width=page["width"],
        page_height=page["height"],
        background_data_url=_background_data_url(working_design.get("background")),
        initial_layers=design_store.prepare_layers_for_canvas(competition_id, working_design.get("layers", [])),
        font_faces=design_store.build_font_faces(),
        revision=st.session_state[revision_key],
        key=f"urkunde_canvas__{competition_id}"
    )

    if canvas_result and "layers" in canvas_result:
        working_design["layers"] = canvas_result["layers"]

    st.session_state[working_key] = working_design

    st.divider()

    preview_col, save_col, reset_col = st.columns(3)

    if preview_col.button("👁️ Vorschau (echtes PDF)", use_container_width=True, key=f"urkunde_preview__{competition_id}"):
        overlay_reader = urkunde_generator.render_urkunde_overlay(working_design, dict(SAMPLE_URKUNDE_CONTEXT))
        st.session_state[f"urkunde_preview_png__{competition_id}"] = _pdf_page_to_png(overlay_reader)

    if save_col.button("💾 Speichern", type="primary", use_container_width=True, key=f"urkunde_save__{competition_id}"):
        design_to_save = copy.deepcopy(working_design)

        background = design_to_save.get("background") or {}
        if background.get("type") == "image" and background.get("data") and not background.get("path"):
            background["path"] = design_store.save_background_bytes(
                competition_id, background["data"], ext=background.get("ext", ".png")
            )
            background.pop("data", None)
            background.pop("ext", None)
        design_to_save["background"] = background

        design_to_save["layers"] = design_store.persist_layer_images(competition_id, design_to_save.get("layers", []))

        design_store.save_urkunde_design(competition_id, design_to_save)
        st.session_state[working_key] = design_to_save
        st.success("Design gespeichert. Wird ab jetzt für Urkunden dieser Competition verwendet.")

    if reset_col.button("↩️ Zurücksetzen", use_container_width=True, key=f"urkunde_reset__{competition_id}"):
        st.session_state[working_key] = design_store.default_urkunde_design()
        st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1
        st.session_state.pop(orientation_key, None)
        st.rerun()

    st.caption(
        "Änderungen im Editor gelten erst nach 'Speichern' dauerhaft für diese Competition."
    )

    download_zip = design_store.export_design_to_zip(working_design)

    st.download_button(
        "⬇️ Vorlage herunterladen (.zip)",
        data=download_zip,
        file_name=f"urkunden_design_{competition_id}.zip",
        mime="application/zip",
        use_container_width=True,
        key=f"urkunde_download__{competition_id}"
    )

    preview_png = st.session_state.get(f"urkunde_preview_png__{competition_id}")

    if preview_png:
        st.image(preview_png, caption="Vorschau (Beispieldaten, echtes PDF-Rendering)", width=400)


def _pdf_page_to_png(pdf_reader):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_page(pdf_reader.pages[0])

    buffer = BytesIO()
    writer.write(buffer)

    return design_store.render_preview_png(buffer.getvalue())


def render_namensschild_design_studio(competition_id):
    st.header("🎨 Namensschild-Design")

    st.write(
        "Lade ein alternatives Competition-Logo für die Namensschilder dieser "
        "Competition hoch und passe dessen Größe an."
    )

    design = design_store.get_namensschild_design(competition_id)
    current_logo_path = design.get("logo_path")

    if current_logo_path:
        st.caption(f"Aktuelles Logo: {current_logo_path}")
        st.image(current_logo_path, width=200)
    else:
        st.caption("Aktuell: Standard-Logo (assets/Logo.png)")

    uploaded_logo = st.file_uploader(
        "Neues Competition-Logo hochladen (PNG)",
        type=["png"],
        key=f"namensschild_logo_upload__{competition_id}"
    )

    logo_scale_percent = st.slider(
        "Logo-Größe",
        min_value=30, max_value=200,
        value=int(round(design.get("logo_scale", 1.0) * 100)),
        step=5, format="%d%%",
        key=f"namensschild_logo_scale__{competition_id}"
    )
    logo_scale = logo_scale_percent / 100.0

    preview_col, save_col, reset_col = st.columns(3)

    if preview_col.button("👁️ Vorschau aktualisieren", use_container_width=True, key=f"badge_preview_btn__{competition_id}"):
        preview_logo = uploaded_logo.getvalue() if uploaded_logo is not None else current_logo_path

        pdf_bytes = _render_badge_preview_pdf(preview_logo, logo_scale)
        st.session_state[f"badge_preview_png__{competition_id}"] = design_store.render_preview_png(pdf_bytes)

    if save_col.button("💾 Speichern", type="primary", use_container_width=True, key=f"badge_save_btn__{competition_id}"):
        logo_path = current_logo_path

        if uploaded_logo is not None:
            logo_path = design_store.save_namensschild_logo(competition_id, uploaded_logo)

        design_store.save_namensschild_design(competition_id, {"logo_path": logo_path, "logo_scale": logo_scale})
        st.success("Gespeichert. Wird ab jetzt für Namensschilder dieser Competition verwendet.")

    if reset_col.button("↩️ Zurücksetzen", use_container_width=True, key=f"badge_reset_btn__{competition_id}"):
        design_store.save_namensschild_design(competition_id, dict(design_store.DEFAULT_NAMENSSCHILD_DESIGN))
        st.rerun()

    preview_png = st.session_state.get(f"badge_preview_png__{competition_id}")

    if preview_png:
        st.image(preview_png, caption="Vorschau (Beispieldaten)", width=500)


def _render_badge_preview_pdf(logo_path, logo_scale=1.0):
    packet = BytesIO()
    page_size = landscape(A4)
    width, height = page_size

    c = pdfcanvas.Canvas(packet, pagesize=page_size)

    def draw_face(canvas_obj):
        wca_common.draw_badge_face(
            canvas_obj, "Max Mustermann", "333", 1, "8.42",
            logo_path=logo_path, logo_scale=logo_scale
        )

    wca_common.render_badge_pair(c, width, height, draw_face)
    c.save()
    packet.seek(0)

    return packet.read()
