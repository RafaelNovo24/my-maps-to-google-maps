"""Lightweight UI string translations for the app.

Holds the Portuguese and English translation tables and the :func:`t` lookup
helper used throughout the interface.
"""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt": {
        "title": "My Maps → Google Maps",
        "subtitle": (
            "Transforme uma rota do Google My Maps em ligações do Google Maps, "
            "troço a troço."
        ),
        "language_label": "Idioma",
        "travel_mode_label": "Modo de deslocação",
        "mode_driving": "De carro",
        "mode_walking": "A pé",
        "mode_bicycling": "De bicicleta",
        "mode_two-wheeler": "De mota",
        "mode_transit": "Transportes públicos",
        "upload_label": "Escolha um ficheiro .kml",
        "no_stretches_warning": "Não foram encontrados troços de rota neste ficheiro.",
        "intro_caption": (
            "Cada ligação abre com um ponto de partida vazio, para indicar o seu próprio início. "
            "Troços longos são divididos em várias ligações (até 9 paragens cada)."
        ),
        "summary_heading": "Resumo da viagem",
        "col_num": "#",
        "col_description": "Descrição",
        "col_distance": "Distância",
        "col_time": "Tempo est.",
        "col_maps": "Google Maps",
        "open_in_maps": "Abrir",
        "links_count": "{n} ligações",
        "total_distance": "Distância total",
        "total_time": "Tempo total est.",
        "stretch_word": "Troço",
        "link_n_of_m": "ligação {i} de {n}",
        "eta_unavailable": "indisponível",
        "eta_needs_key": "Defina GOOGLE_MAPS_API_KEY para mostrar distância e tempo.",
        "gpx_section_header": "Converter KML para GPX",
        "gpx_convert_button": "Converter para GPX",
        "gpx_converting": "A converter…",
        "gpx_download_button": "Transferir GPX",
        "gpx_error": "Não foi possível converter este KML para GPX.",
        "gpx_no_data": "Não há percursos nem marcadores para converter neste ficheiro.",
        "gpx_skipped": "{n} forma(s) ignorada(s) (o GPX não suporta polígonos).",
        "gpx_jump_button": "Conversor KML → GPX ↓",
    },
    "en": {
        "title": "My Maps → Google Maps",
        "subtitle": "Turn a Google My Maps route into Google Maps links, stretch by stretch.",
        "language_label": "Language",
        "travel_mode_label": "Travel mode",
        "mode_driving": "Driving",
        "mode_walking": "Walking",
        "mode_bicycling": "Bicycling",
        "mode_two-wheeler": "Two-wheeler",
        "mode_transit": "Transit",
        "upload_label": "Choose a .kml file",
        "no_stretches_warning": "No route stretches found in this file.",
        "intro_caption": (
            "Each link opens with an empty start, so you can add your own starting point. "
            "Long stretches are split into several links (up to 9 stops each)."
        ),
        "summary_heading": "Journey summary",
        "col_num": "#",
        "col_description": "Description",
        "col_distance": "Distance",
        "col_time": "Est. time",
        "col_maps": "Google Maps",
        "open_in_maps": "Open",
        "links_count": "{n} links",
        "total_distance": "Total distance",
        "total_time": "Total est. time",
        "stretch_word": "Stretch",
        "link_n_of_m": "link {i} of {n}",
        "eta_unavailable": "unavailable",
        "eta_needs_key": "Set GOOGLE_MAPS_API_KEY to show distance & time.",
        "gpx_section_header": "Convert KML to GPX",
        "gpx_convert_button": "Convert to GPX",
        "gpx_converting": "Converting…",
        "gpx_download_button": "Download GPX",
        "gpx_error": "Could not convert this KML to GPX.",
        "gpx_no_data": "No tracks or pins to convert in this file.",
        "gpx_skipped": "{n} shape(s) skipped (GPX has no polygons).",
        "gpx_jump_button": "KML → GPX converter ↓",
    },
}

DEFAULT_LANG = "pt"
LANGUAGES = ["pt", "en"]


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: object) -> str:
    """Look up a translated string and optionally format it.

    Falls back to the English translation, then to the key itself, when the
    requested language has no entry for the key.

    Args:
        key (str): The translation key to look up.
        lang (str, optional): The language code to translate into. Defaults to
            DEFAULT_LANG.
        **kwargs (object): Values substituted into the template via
            ``str.format`` when any are provided.

    Returns:
        str: The translated (and, when keyword arguments are given, formatted)
            string.
    """
    lang_table = TRANSLATIONS.get(lang, {})
    template = lang_table.get(key) or TRANSLATIONS.get("en", {}).get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template
