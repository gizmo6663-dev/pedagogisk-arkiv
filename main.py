import os
import json
import threading
import time
import traceback
import webbrowser
import sqlite3
import concurrent.futures
from urllib.parse import quote_plus, urljoin

from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.animation import Animation
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDFillRoundFlatButton, MDFloatingActionButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.selectioncontrol import MDSwitch
import requests
import certifi

# --- SSL-KONFIGURASJON FOR ANDROID ---
# Dette er avgjørende for at appen ikke skal krasje ved internett-søk
os.environ['SSL_CERT_FILE'] = certifi.where()

# --- Konstanter ---
OPENALEX_FIELDS = (
    "id,doi,display_name,publication_year,"
    "authorships,abstract_inverted_index,concepts,primary_location"
)
PEDAGOGY_FILTER = (
    "concepts.display_name:"
    "education|pedagogy|psychology|sociology|child development"
)
# Replace with your app's contact email to use the OpenAlex "polite pool"
MAILTO = "din-epost@example.com"
CACHE_TTL = 3600  # sekunder (1 time)
SCROLL_TOP_THRESHOLD = 0.98  # scroll_y-verdi som anses som "toppen"


# --- Database ---
def init_db():
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved
                      (id TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS search_cache
                      (query TEXT PRIMARY KEY, results_json TEXT, timestamp INTEGER)''')
    conn.commit()
    conn.close()


def get_cached(cache_key):
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT results_json, timestamp FROM search_cache WHERE query = ?",
        (cache_key,)
    )
    row = cursor.fetchone()
    conn.close()
    if row and 0 <= time.time() - row[1] < CACHE_TTL:
        return json.loads(row[0])
    return None


def set_cache(cache_key, data):
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO search_cache (query, results_json, timestamp) VALUES (?, ?, ?)",
        (cache_key, json.dumps(data), int(time.time()))
    )
    conn.commit()
    conn.close()


# --- Hjelpefunksjoner ---
def reconstruct_abstract(inverted_index):
    """Rekonstruerer sammendrag fra OpenAlex abstract_inverted_index."""
    if not inverted_index:
        return ""
    positions = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    text = " ".join(positions[i] for i in sorted(positions.keys()))
    return text[:220] + "..." if len(text) > 220 else text


def normalize_url(work):
    """Bygger en gyldig URL fra OpenAlex-verkets metadata."""
    doi = work.get("doi")
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    pl = work.get("primary_location") or {}
    landing = pl.get("landing_page_url")
    if not landing and isinstance(pl.get("source"), dict):
        landing = pl["source"].get("landing_page_url")
    return landing or work.get("id") or "https://openalex.org"


# --- Datahenting ---
def fetch_openalex(query, open_access_only, sort_newest):
    """Henter artikler fra OpenAlex API med fagfilter og relevansssortering."""
    encoded = quote_plus(query)
    sort = "publication_year:desc" if sort_newest else "relevance_score:desc"
    oa_filter = "open_access.is_oa:true" if open_access_only else ""

    def build_url(include_concept_filter):
        filters = []
        if include_concept_filter:
            filters.append(PEDAGOGY_FILTER)
        if oa_filter:
            filters.append(oa_filter)
        filter_param = f"&filter={','.join(filters)}" if filters else ""
        return (
            f"https://api.openalex.org/works"
            f"?search={encoded}"
            f"&per_page=25"
            f"&sort={sort}"
            f"{filter_param}"
            f"&select={OPENALEX_FIELDS}"
            f"&mailto={MAILTO}"
        )

    works = []
    # Prøv med fagfilter først; fall tilbake uten filter om ingen treff
    for include_filter in (True, False):
        try:
            resp = requests.get(build_url(include_filter), timeout=12)
            if resp.status_code == 200:
                works = resp.json().get("results", [])
                if works:
                    break
        except Exception:
            print(traceback.format_exc())

    results = []
    for work in works:
        if not work.get("display_name"):
            continue
        authorships = work.get("authorships", [])
        authors = [
            a["author"]["display_name"]
            for a in authorships[:3]
            if a.get("author") and a["author"].get("display_name")
        ]
        author_str = ", ".join(authors)
        if len(authorships) > 3:
            author_str += " et al."
        results.append({
            'title': work["display_name"],
            'year': work.get("publication_year") or "N/A",
            'source': "OPENALEX",
            'url': normalize_url(work),
            'abstract': reconstruct_abstract(work.get("abstract_inverted_index")),
            'authors': author_str,
        })

    # Henter toppbegreper fra første treff for "Relaterte søk"
    concepts = [
        c["display_name"]
        for c in (works[0].get("concepts", [])[:5] if works else [])
        if c.get("display_name")
    ]
    return results, concepts


def fetch_eric(query):
    """Henter artikler fra ERIC (US Department of Education).
    ERIC har ikke innebygd åpen-tilgang-filter via API."""
    encoded = quote_plus(query)
    fields = "title,author,publicationdateyear,url,description"
    url = (
        f"https://api.ies.ed.gov/eric/"
        f"?search={encoded}&fields={fields}&format=json&rows=15"
    )
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for doc in data.get("response", {}).get("docs", []):
            title = doc.get("title") or ""
            if not title:
                continue
            raw_authors = doc.get("author") or []
            if isinstance(raw_authors, list):
                author_str = ", ".join(raw_authors[:3])
                if len(raw_authors) > 3:
                    author_str += " et al."
            else:
                author_str = str(raw_authors) if raw_authors else ""
            year = doc.get("publicationdateyear") or "N/A"
            article_url = doc.get("url") or f"https://eric.ed.gov/?q={encoded}"
            if article_url and not article_url.startswith("http"):
                article_url = urljoin("https://eric.ed.gov/", article_url)
            description = doc.get("description") or ""
            if len(description) > 220:
                description = description[:217] + "..."
            results.append({
                'title': title,
                'year': str(year),
                'source': "ERIC",
                'url': article_url,
                'abstract': description,
                'authors': author_str,
            })
        return results
    except Exception:
        print(traceback.format_exc())
        return []


# --- Design og Layout ---
KV = '''
MDScreen:
    md_bg_color: "#EEF2F7"

    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: "Pedagogisk Fagarkiv"
            elevation: 2
            md_bg_color: "#1A237E"
            specific_text_color: "#FFFFFF"
            right_action_items: [["bookmark-outline", lambda x: app.show_saved()], ["history", lambda x: app.clear_results()]]

        MDScrollView:
            id: scroll_view
            do_scroll_x: False
            on_scroll_y: app.on_scroll(self, self.scroll_y)

            MDBoxLayout:
                orientation: 'vertical'
                adaptive_height: True
                padding: [0, 0, 0, dp(80)]

                # Hero-seksjon (Blå bue)
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    md_bg_color: "#1A237E"
                    padding: [dp(24), dp(16), dp(24), dp(48)]
                    radius: [0, 0, dp(30), dp(30)]
                    spacing: dp(16)

                    MDLabel:
                        text: "Søk i verdens største forskningsarkiv"
                        theme_text_color: "Custom"
                        text_color: "#FFFFFF"
                        font_style: "H6"
                        halign: "center"

                    # Søkefelt med tøm-knapp
                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(56)
                        spacing: dp(6)

                        MDTextField:
                            id: search_input
                            hint_text: "Hva vil du lære mer om?"
                            mode: "round"
                            fill_color_normal: "#FFFFFF"
                            on_text_validate: app.trigger_search()

                        MDIconButton:
                            id: clear_search_btn
                            icon: "close-circle-outline"
                            theme_text_color: "Custom"
                            text_color: "#BBCDE8"
                            size_hint: (None, None)
                            size: dp(48), dp(48)
                            pos_hint: {"center_y": 0.5}
                            on_release: app.clear_search_input()

                    MDFillRoundFlatButton:
                        id: search_button
                        text: "HENT ARTIKLER"
                        md_bg_color: "#FF8F00"
                        text_color: "#FFFFFF"
                        pos_hint: {"center_x": .5}
                        on_release: app.trigger_search()

                    # Filtervalgene – fikset layout
                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(48)
                        spacing: dp(24)
                        padding: [dp(8), dp(4), dp(8), dp(4)]

                        MDBoxLayout:
                            spacing: dp(10)

                            MDSwitch:
                                id: oa_toggle
                                active: False
                                size_hint_x: None
                                width: dp(52)
                                pos_hint: {"center_y": 0.5}

                            MDLabel:
                                text: "Kun åpen tilgang"
                                theme_text_color: "Custom"
                                text_color: "#FFFFFF"
                                font_style: "Caption"
                                size_hint_y: None
                                height: dp(40)
                                valign: "center"

                        MDBoxLayout:
                            spacing: dp(10)

                            MDSwitch:
                                id: sort_toggle
                                active: False
                                size_hint_x: None
                                width: dp(52)
                                pos_hint: {"center_y": 0.5}

                            MDLabel:
                                text: "Nyeste først"
                                theme_text_color: "Custom"
                                text_color: "#FFFFFF"
                                font_style: "Caption"
                                size_hint_y: None
                                height: dp(40)
                                valign: "center"

                # Resultat-område
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    padding: [dp(16), dp(20), dp(16), dp(8)]
                    spacing: dp(16)

                    MDLabel:
                        id: info_label
                        text: "Søker i OpenAlex og ERIC"
                        theme_text_color: "Hint"
                        font_style: "Caption"
                        halign: "center"

                    # Relaterte søk (chips)
                    MDBoxLayout:
                        id: chips_box
                        adaptive_height: True
                        spacing: dp(8)
                        padding: [dp(4), 0, dp(4), dp(4)]

                    MDList:
                        id: results_list
                        spacing: dp(12)

    # Rull-til-topp-knapp (FAB)
    MDFloatingActionButton:
        id: scroll_top_btn
        icon: "chevron-up"
        md_bg_color: "#1A237E"
        elevation: 4
        pos_hint: {"right": 0.97, "y": 0.04}
        opacity: 0
        disabled: True
        on_release: app.scroll_to_top()
'''


class PedagogiskApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        init_db()
        return Builder.load_string(KV)

    def on_scroll(self, scroll_view, scroll_y):
        """Viser/skjuler rull-til-topp-knappen basert på scroll-posisjon."""
        fab = self.root.ids.scroll_top_btn
        if scroll_y < SCROLL_TOP_THRESHOLD:
            if fab.opacity == 0:
                fab.disabled = False
                Animation(opacity=1, duration=0.2).start(fab)
        else:
            if fab.opacity > 0:
                anim = Animation(opacity=0, duration=0.2)
                anim.bind(on_complete=lambda *a: setattr(fab, 'disabled', True))
                anim.start(fab)

    def scroll_to_top(self):
        """Ruller til toppen av listen."""
        Animation(scroll_y=1, duration=0.4, t='out_quad').start(
            self.root.ids.scroll_view
        )

    def clear_search_input(self):
        """Tømmer søkefeltet."""
        self.root.ids.search_input.text = ""

    def trigger_search(self):
        query = self.root.ids.search_input.text.strip()
        if not query:
            return
        self.root.ids.search_button.disabled = True
        self.root.ids.results_list.clear_widgets()
        self.root.ids.chips_box.clear_widgets()
        self.root.ids.info_label.text = "Kobler til arkivet..."
        open_access = self.root.ids.oa_toggle.active
        sort_newest = self.root.ids.sort_toggle.active
        # Kjører nettverkskall i bakgrunnstråd for å holde UI flytende
        threading.Thread(
            target=self.perform_search,
            args=(query, open_access, sort_newest),
            daemon=True
        ).start()

    def perform_search(self, query, open_access_only, sort_newest):
        cache_key = f"{query}|{open_access_only}|{sort_newest}"
        cached = get_cached(cache_key)
        if cached:
            Clock.schedule_once(
                lambda dt: self._display_results(
                    cached['results'], cached.get('concepts', [])
                ), 0
            )
            return

        results = []
        concepts = []
        # Henter fra OpenAlex og ERIC parallelt
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            oa_future = executor.submit(
                fetch_openalex, query, open_access_only, sort_newest
            )
            eric_future = executor.submit(fetch_eric, query)

            try:
                oa_results, concepts = oa_future.result()
                results.extend(oa_results)
            except Exception:
                print(traceback.format_exc())

            try:
                eric_results = eric_future.result()
            except Exception:
                print(traceback.format_exc())
                eric_results = []

        # Slår sammen og fjerner duplikater (foretrekker DOI/URL-nøkkel, faller tilbake til tittel)
        def dedup_key(item):
            url = item.get('url', '')
            if url and 'doi.org/' in url:
                return url.lower()
            return item['title'].lower()

        seen = {dedup_key(r) for r in results}
        for item in eric_results:
            key = dedup_key(item)
            if key not in seen:
                results.append(item)
                seen.add(key)

        set_cache(cache_key, {'results': results, 'concepts': concepts})
        Clock.schedule_once(lambda dt: self._display_results(results, concepts), 0)

    def _display_results(self, results, concepts):
        self.root.ids.results_list.clear_widgets()
        if results:
            for item in results:
                self.add_modern_card(item)
            self.root.ids.info_label.text = f"Fant {len(results)} kilder"
        else:
            self.root.ids.info_label.text = "Ingen treff. Prøv et annet ord."
        self._show_chips(concepts)
        self.root.ids.search_button.disabled = False

    def _show_chips(self, concepts):
        box = self.root.ids.chips_box
        box.clear_widgets()
        for concept in concepts[:5]:
            btn = MDFillRoundFlatButton(
                text=concept,
                font_size="11sp",
                md_bg_color="#FF8F00",
                text_color="#FFFFFF",
                size_hint=(None, None),
                height=dp(32),
                on_release=lambda x, q=concept: self._search_related(q)
            )
            box.add_widget(btn)

    def _search_related(self, query):
        self.root.ids.search_input.text = query
        self.trigger_search()

    def add_modern_card(self, item):
        has_authors = bool(item.get('authors'))
        has_abstract = bool(item.get('abstract'))

        source_colors = {"OPENALEX": "#1565C0", "ERIC": "#00695C"}
        source_color = source_colors.get(item['source'], "#1A237E")

        card = MDCard(
            orientation='vertical',
            padding=dp(16),
            spacing=dp(6),
            size_hint_x=1,
            adaptive_height=True,
            elevation=2,
            radius=[dp(16)],
            md_bg_color="#FFFFFF"
        )

        # Topplinje med kilde og år
        header = MDBoxLayout(adaptive_height=True, spacing=dp(4))
        source_lbl = MDLabel(
            text=item['source'], font_style="Caption",
            theme_text_color="Custom", text_color=source_color, bold=True,
            size_hint_x=0.7, adaptive_height=True,
            halign="left", valign="center"
        )
        source_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        header.add_widget(source_lbl)
        year_lbl = MDLabel(
            text=str(item['year']), font_style="Caption",
            theme_text_color="Custom", text_color="#757575",
            size_hint_x=0.3, adaptive_height=True,
            halign="right", valign="center"
        )
        year_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        header.add_widget(year_lbl)
        card.add_widget(header)

        # Tittel
        title_lbl = MDLabel(
            text=item['title'], font_style="Subtitle1", bold=True,
            theme_text_color="Custom", text_color="#212121",
            adaptive_height=True, halign="left", valign="top"
        )
        title_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        card.add_widget(title_lbl)

        # Forfattere
        if has_authors:
            auth_lbl = MDLabel(
                text=f"Forfattere: {item['authors']}",
                font_style="Caption",
                theme_text_color="Custom", text_color="#616161",
                adaptive_height=True, halign="left", valign="top"
            )
            auth_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
            card.add_widget(auth_lbl)

        # Sammendrag
        if has_abstract:
            abs_lbl = MDLabel(
                text=item['abstract'],
                font_style="Caption",
                theme_text_color="Custom", text_color="#424242",
                adaptive_height=True, halign="left", valign="top"
            )
            abs_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
            card.add_widget(abs_lbl)

        # Knapper
        actions = MDBoxLayout(adaptive_height=True, spacing=dp(10),
                              padding=[0, dp(6), 0, 0])
        actions.add_widget(MDFillRoundFlatButton(
            text="LES MER", font_size="12sp", md_bg_color="#1A237E",
            text_color="#FFFFFF",
            on_release=lambda x, url=item['url']: webbrowser.open(url)
        ))
        actions.add_widget(MDIconButton(
            icon="bookmark-plus-outline", theme_text_color="Custom", text_color="#1A237E",
            on_release=lambda x, i=item: self.save_to_db(i)
        ))
        card.add_widget(actions)
        self.root.ids.results_list.add_widget(card)

    def save_to_db(self, item):
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO saved VALUES (?, ?, ?, ?)",
                (str(item['url']), item['title'], item['source'], item['url'])
            )
            conn.commit()
            self.root.ids.info_label.text = "Lagret i ditt arkiv!"
        except Exception:
            self.root.ids.info_label.text = "Allerede lagret."
        conn.close()

    def show_saved(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.chips_box.clear_widgets()
        self.root.ids.info_label.text = "Ditt personlige fagarkiv"
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            self.add_modern_card({
                'title': row[1], 'source': row[2],
                'year': 'Arkiv', 'url': row[3],
                'abstract': '', 'authors': ''
            })

    def clear_results(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.chips_box.clear_widgets()
        self.root.ids.search_input.text = ""
        self.root.ids.info_label.text = "Søk tømt"


if __name__ == "__main__":
    PedagogiskApp().run()
