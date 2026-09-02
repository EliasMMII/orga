import os
import sys
import io
import zipfile
import requests
import streamlit as st

import namenschild_live
import namenschild_round1
import urkunde_generator
import wca_common
import design_studio


st.set_page_config(
    page_title="WCA Generator",
    page_icon="🏆",
    layout="centered"
)


EVENT_NAMES = wca_common.EVENT_NAMES


def get_wcif(competition_id):
    return wca_common.fetch_wcif(competition_id)


@st.cache_data(ttl=300)
def get_ongoing_competitions():
    try:
        return wca_common.fetch_ongoing_competitions()
    except Exception:
        return []


def get_available_events(wcif):
    events = []

    for event in wcif.get("events", []):
        event_id = event.get("id")

        if event_id in EVENT_NAMES:
            events.append(event_id)

    return events


def get_rounds(wcif, event_id):
    for event in wcif.get("events", []):
        if event.get("id") == event_id:
            return event.get("rounds", [])

    return []


def get_final_round(wcif, event_id):
    rounds = get_rounds(
        wcif,
        event_id
    )

    if not rounds:
        return None

    return rounds[-1]


def is_final_finished(wcif, event_id):
    final_round = get_final_round(
        wcif,
        event_id
    )

    if not final_round:
        return False

    results = final_round.get(
        "results",
        []
    )

    if not results:
        return False

    for result in results:
        ranking = result.get("ranking")

        if (
            ranking is not None
            and ranking > 0
        ):
            return True

    return False


def get_event_status(wcif, event_id):
    rounds = get_rounds(
        wcif,
        event_id
    )

    if not rounds:
        return "Keine Runde"

    final_round = rounds[-1]

    results = final_round.get(
        "results",
        []
    )

    if not results:
        return "Finale noch nicht beendet"

    valid_results = [
        result
        for result in results
        if (
            result.get("ranking") is not None
            and result.get("ranking") > 0
        )
    ]

    if not valid_results:
        return "Finale noch nicht beendet"

    return "Finale abgeschlossen"


def generate_namenschilder(
    competition_id,
    event_id,
    round_number,
    count
):
    output_filename = (
        f"Namenschilder_Live_"
        f"{competition_id}_"
        f"{event_id}-r{round_number}_"
        f"Top{count}.pdf"
    )

    output_path = os.path.join(
        os.getcwd(),
        output_filename
    )

    if os.path.exists(output_path):
        os.remove(output_path)

    namenschild_live.generate_live_badges(
        competition_id,
        event_id,
        round_number,
        count
    )

    if os.path.exists(output_path):
        return output_path

    return None


def generate_namenschilder_round1(
    competition_id,
    event_id,
    wcif
):
    output_filename = (
        f"Namensschilder_Round1_"
        f"{competition_id}_"
        f"{event_id}.pdf"
    )

    output_path = os.path.join(
        os.getcwd(),
        output_filename
    )

    if os.path.exists(output_path):
        os.remove(output_path)

    return namenschild_round1.generate_round1_badges(
        wcif,
        event_id,
        output_pdf=output_path
    )


def generate_urkunden(
    competition_id,
    event_id,
    country_code=None
):
    suffix = ""

    if country_code:
        suffix = f"_{country_code}"

    output_dir = getattr(
        urkunde_generator,
        "OUTPUT_DIR",
        "Urkunden_Gesamt"
    )

    output_path = os.path.join(
        output_dir,
        f"Urkunden_{event_id.upper()}{suffix}.pdf"
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    if os.path.exists(output_path):
        os.remove(output_path)

    original_argv = sys.argv.copy()

    try:
        sys.argv = [
            "urkunde_generator.py",
            competition_id,
            event_id
        ]

        if country_code:
            sys.argv.append(country_code)

        urkunde_generator.main()

    finally:
        sys.argv = original_argv

    if os.path.exists(output_path):
        return output_path

    return None


def add_generated_file(path):
    if not path or not os.path.exists(path):
        return False

    with open(path, "rb") as file:
        data = file.read()

    filename = os.path.basename(path)

    for existing in st.session_state.generated_files:
        if existing["filename"] == filename:
            existing["data"] = data
            return True

    st.session_state.generated_files.append(
        {
            "filename": filename,
            "data": data
        }
    )

    return True


def create_zip(files):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for file_data in files:
            zip_file.writestr(
                file_data["filename"],
                file_data["data"]
            )

    zip_buffer.seek(0)

    return zip_buffer.getvalue()


# ============================================================
# SESSION STATE
# ============================================================

if "competition_loaded" not in st.session_state:
    st.session_state.competition_loaded = False

if "competition_id" not in st.session_state:
    st.session_state.competition_id = None

if "wcif" not in st.session_state:
    st.session_state.wcif = None

if "generated_files" not in st.session_state:
    st.session_state.generated_files = []


# ============================================================
# TITEL
# ============================================================

st.title("🏆 WCA Generator")

st.write(
    "Erstelle Namensschilder und Urkunden "
    "für WCA-Competitions."
)


# ============================================================
# COMPETITION LADEN
# ============================================================

def load_competition(entered_id):

    if not entered_id:

        st.warning(
            "Bitte eine Competition-ID eingeben."
        )

        return

    try:

        with st.spinner(
            "Lade Competition..."
        ):

            loaded_wcif = get_wcif(
                entered_id
            )

        st.session_state.competition_id = (
            entered_id
        )

        st.session_state.wcif = (
            loaded_wcif
        )

        st.session_state.competition_loaded = True

        st.session_state.generated_files = []

        st.rerun()

    except requests.HTTPError:

        st.error(
            "Die Competition-ID wurde nicht gefunden "
            "oder die WCA-Daten konnten nicht geladen werden."
        )

    except Exception as e:

        st.error(
            f"Fehler beim Laden der Competition: {e}"
        )


if not st.session_state.competition_loaded:

    st.header("1. Competition laden")

    ongoing_competitions = get_ongoing_competitions()

    if ongoing_competitions:

        st.subheader("Aktuell laufende Competitions")

        for competition in ongoing_competitions:

            label = (
                f"{competition['name']} "
                f"({competition.get('country_iso2', '?')}, "
                f"{competition.get('date_range', '')})"
            )

            if st.button(
                label,
                use_container_width=True,
                key=f"ongoing_{competition['id']}"
            ):

                load_competition(competition["id"])

        st.divider()
        st.subheader("Oder Competition-ID manuell eingeben")

    else:

        st.info(
            "Aktuell laufen laut WCA keine Competitions."
        )

    competition_id_input = st.text_input(
        "WCA Competition-ID",
        placeholder="z. B. CapelleChaosB2026"
    )

    if st.button(
        "📥 Competition laden",
        type="primary",
        use_container_width=True,
        key="load_competition_button"
    ):

        load_competition(competition_id_input.strip())

    st.info(
        "Gib die Competition-ID aus der WCA ein, "
        "z. B. **CapelleChaosB2026**."
    )

    st.stop()


# ============================================================
# GELADENE COMPETITION
# ============================================================

competition_id = (
    st.session_state.competition_id
)

wcif = (
    st.session_state.wcif
)


st.header("1. Competition")

st.success(
    f"Ausgewählt: **{wcif.get('name', competition_id)}**"
)

st.caption(
    f"Competition-ID: {competition_id}"
)


if st.button(
    "🔄 Andere Competition laden",
    use_container_width=True,
    key="change_competition_button"
):

    st.session_state.competition_loaded = False
    st.session_state.competition_id = None
    st.session_state.wcif = None
    st.session_state.generated_files = []

    st.rerun()


# ============================================================
# EVENTS AUS DER BEREITS GELADENEN WCIF
# ============================================================

available_events = get_available_events(
    wcif
)


if not available_events:

    st.error(
        "Für diese Competition wurden keine "
        "bekannten Events gefunden."
    )

    st.stop()


st.divider()


# ============================================================
# AUSGABE
# ============================================================

st.header("2. Ausgabe auswählen")


generator_type = st.radio(
    "Was möchtest du erstellen?",
    [
        "Namensschilder (Live-Ergebnisse)",
        "Namensschilder (Runde 1 / Seeding)",
        "Urkunden",
        "🎨 Design: Urkunden",
        "🎨 Design: Namensschilder"
    ],
    horizontal=True,
    key="generator_type"
)


st.divider()


# ============================================================
# NAMENSSCHILDER (LIVE-ERGEBNISSE)
# ============================================================

if generator_type == "Namensschilder (Live-Ergebnisse)":

    st.header("🏷️ Namensschilder (Live-Ergebnisse)")

    event_labels = []

    for event_id in available_events:

        event_name = EVENT_NAMES.get(
            event_id,
            event_id.upper()
        )

        event_labels.append(
            f"{event_name} ({event_id})"
        )


    selected_event_label = st.selectbox(
        "Event",
        event_labels,
        key="badge_event_select"
    )


    event_id = (
        selected_event_label
        .split("(")[-1]
        .rstrip(")")
    )


    rounds = get_rounds(
        wcif,
        event_id
    )


    if not rounds:

        st.error(
            "Für dieses Event wurden keine "
            "Runden gefunden."
        )

        st.stop()


    round_options = {}


    for round_data in rounds:

        round_id = round_data.get(
            "id",
            ""
        )

        try:

            round_number = int(
                round_id.split("-r")[-1]
            )

        except ValueError:

            continue


        round_name = round_data.get(
            "name",
            f"Runde {round_number}"
        )


        round_options[
            f"{round_name} "
            f"(Runde {round_number})"
        ] = round_number


    if not round_options:

        st.error(
            "Keine gültigen Runden gefunden."
        )

        st.stop()


    selected_round_label = st.selectbox(
        "Runde",
        list(
            round_options.keys()
        ),
        key="badge_round_select"
    )


    round_number = round_options[
        selected_round_label
    ]


    st.subheader("Anzahl")


    count = st.number_input(
        "Anzahl der Teilnehmer",
        min_value=1,
        max_value=1000,
        value=16,
        step=1,
        key="badge_count"
    )


    st.divider()


    if st.button(
        "🏷️ Namensschilder erstellen",
        type="primary",
        use_container_width=True,
        key="generate_badges_button"
    ):

        with st.spinner(
            "Namensschilder werden erstellt..."
        ):

            try:

                output_path = generate_namenschilder(
                    competition_id,
                    event_id,
                    round_number,
                    count
                )

            except Exception as e:

                st.error(
                    f"Fehler beim Erstellen: {e}"
                )

                output_path = None


        if (
            output_path
            and os.path.exists(output_path)
        ):

            add_generated_file(
                output_path
            )

            st.success(
                f"{count} Namensschilder wurden erstellt."
            )

        else:

            st.error(
                "Die PDF-Datei konnte nicht gefunden werden."
            )


# ============================================================
# NAMENSSCHILDER (RUNDE 1 / SEEDING)
# ============================================================

elif generator_type == "Namensschilder (Runde 1 / Seeding)":

    st.header("🏷️ Namensschilder (Runde 1 / Seeding)")

    st.write(
        "Erstellt Namensschilder für alle angemeldeten Teilnehmer eines "
        "Events, sortiert nach ihrem WCA-Seeding (Personal Best) – "
        "geeignet, bevor die erste Runde Ergebnisse hat."
    )

    event_labels_round1 = []

    for event_id in available_events:

        event_name = EVENT_NAMES.get(
            event_id,
            event_id.upper()
        )

        event_labels_round1.append(
            f"{event_name} ({event_id})"
        )

    selected_event_label_round1 = st.selectbox(
        "Event",
        event_labels_round1,
        key="badge_round1_event_select"
    )

    event_id = (
        selected_event_label_round1
        .split("(")[-1]
        .rstrip(")")
    )

    st.divider()

    if st.button(
        "🏷️ Namensschilder erstellen",
        type="primary",
        use_container_width=True,
        key="generate_badges_round1_button"
    ):

        with st.spinner(
            "Namensschilder werden erstellt..."
        ):

            try:

                output_path = generate_namenschilder_round1(
                    competition_id,
                    event_id,
                    wcif
                )

            except Exception as e:

                st.error(
                    f"Fehler beim Erstellen: {e}"
                )

                output_path = None


        if (
            output_path
            and os.path.exists(output_path)
        ):

            add_generated_file(
                output_path
            )

            st.success(
                "Namensschilder wurden erstellt."
            )

        else:

            st.error(
                "Die PDF-Datei konnte nicht gefunden werden."
            )


# ============================================================
# URKUNDEN
# ============================================================

elif generator_type == "Urkunden":

    st.header("🏆 Urkunden")

    st.write(
        "Wähle die Events aus, für die bereits "
        "ein abgeschlossenes Finale vorhanden ist."
    )


    selected_events = []


    for event_id in available_events:

        event_name = EVENT_NAMES.get(
            event_id,
            event_id.upper()
        )

        final_finished = is_final_finished(
            wcif,
            event_id
        )

        status = get_event_status(
            wcif,
            event_id
        )


        checkbox_key = (
            f"certificate_"
            f"{competition_id}_"
            f"{event_id}"
        )


        if final_finished:

            checked = st.checkbox(
                f"✅ {event_name} ({event_id}) – {status}",
                key=checkbox_key
            )

            if checked:

                selected_events.append(
                    event_id
                )

        else:

            st.checkbox(
                f"⚪ {event_name} ({event_id}) – {status}",
                value=False,
                disabled=True,
                key=checkbox_key
            )


    st.divider()


    # ========================================================
    # PODIUM
    # ========================================================

    st.subheader("Podium")


    podium_type = st.radio(
        "Welche Platzierungen sollen "
        "berücksichtigt werden?",
        [
            "Gesamtpodium",
            "Deutschland (DE)"
        ],
        key="podium_type"
    )


    if podium_type == "Deutschland (DE)":

        country_code = "DE"

    else:

        country_code = None


    if country_code:

        st.info(
            "Es werden die besten drei "
            "deutschen Teilnehmer berücksichtigt."
        )

    else:

        st.info(
            "Es werden die ersten drei Plätze "
            "der Gesamtwertung berücksichtigt."
        )


    st.divider()


    # ========================================================
    # AUSWAHL
    # ========================================================

    if selected_events:

        selected_names = []

        for event_id in selected_events:

            selected_names.append(
                EVENT_NAMES.get(
                    event_id,
                    event_id.upper()
                )
            )

        st.success(
            "Ausgewählte Events: "
            + ", ".join(selected_names)
        )

    else:

        st.warning(
            "Noch keine Events ausgewählt."
        )


    # ========================================================
    # URKUNDEN ERZEUGEN
    # ========================================================

    if st.button(
        "🏆 Urkunden für ausgewählte Events erstellen",
        type="primary",
        use_container_width=True,
        disabled=len(selected_events) == 0,
        key="generate_certificates_button"
    ):

        progress = st.progress(0)

        total_events = len(
            selected_events
        )


        for index, event_id in enumerate(
            selected_events
        ):

            event_name = EVENT_NAMES.get(
                event_id,
                event_id.upper()
            )


            with st.spinner(
                f"Erstelle Urkunden für {event_name}..."
            ):

                try:

                    output_path = generate_urkunden(
                        competition_id,
                        event_id,
                        country_code
                    )


                    if (
                        output_path
                        and os.path.exists(
                            output_path
                        )
                    ):

                        add_generated_file(
                            output_path
                        )

                        st.success(
                            f"✅ {event_name} fertig"
                        )

                    else:

                        st.error(
                            f"❌ PDF für {event_name} "
                            f"wurde nicht gefunden."
                        )

                except Exception as e:

                    st.error(
                        f"❌ Fehler bei {event_name}: {e}"
                    )


            progress.progress(
                (index + 1) / total_events
            )


# ============================================================
# DESIGN-STUDIO
# ============================================================

elif generator_type == "🎨 Design: Urkunden":

    design_studio.render_urkunde_design_studio(competition_id)

elif generator_type == "🎨 Design: Namensschilder":

    design_studio.render_namensschild_design_studio(competition_id)


# ============================================================
# GENERIERTE DATEIEN
# ============================================================

generated_files = (
    st.session_state.generated_files
)


if generated_files:

    st.divider()

    st.header("⬇️ Fertige Dateien")


    st.success(
        f"{len(generated_files)} "
        f"Datei(en) wurden erstellt."
    )


    # ========================================================
    # ALLE DATEIEN ALS ZIP
    # ========================================================

    zip_data = create_zip(
        generated_files
    )


    zip_filename = (
        f"WCA_Generator_"
        f"{competition_id}.zip"
    )


    st.download_button(
        label="⬇️ Alle generierten Dateien herunterladen",
        data=zip_data,
        file_name=zip_filename,
        mime="application/zip",
        use_container_width=True,
        type="primary",
        key=f"download_all_{competition_id}"
    )


    st.caption(
        "Alle bisher erzeugten Namensschilder und "
        "Urkunden werden gemeinsam als ZIP-Datei heruntergeladen."
    )


    st.divider()


    # ========================================================
    # EINZELNE DATEIEN
    # ========================================================

    st.subheader("Einzelne Dateien")


    for index, file_data in enumerate(
        generated_files
    ):

        st.download_button(
            label=(
                "⬇️ "
                + file_data["filename"]
            ),
            data=file_data["data"],
            file_name=file_data["filename"],
            mime="application/pdf",
            use_container_width=True,
            key=(
                f"download_single_"
                f"{competition_id}_"
                f"{index}_"
                f"{file_data['filename']}"
            )
        )