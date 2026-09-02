import os

import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design_canvas_component")

_design_canvas = components.declare_component("design_canvas", path=_COMPONENT_DIR)


def design_canvas(page_width, page_height, background_data_url, initial_layers, font_faces, revision, key=None):
    """Rendert den freien Drag-and-Drop-Design-Editor (Fabric.js-Canvas).

    Gibt {"layers": [...]} zurück, sobald der Nutzer im Editor etwas ändert
    (None beim allerersten Rendern, bevor eine Änderung gemeldet wurde).

    revision muss sich ändern (z. B. hochgezählt werden), damit die Canvas
    mit neuen initial_layers neu aufgebaut wird (z. B. nach Reset/Import) -
    bei gleicher revision bleibt der aktuelle Bearbeitungsstand im Browser
    über Streamlit-Reruns hinweg erhalten.
    """
    return _design_canvas(
        pageWidth=page_width,
        pageHeight=page_height,
        backgroundDataUrl=background_data_url,
        initialLayers=initial_layers,
        fontFaces=font_faces,
        revision=revision,
        key=key,
        default=None
    )
