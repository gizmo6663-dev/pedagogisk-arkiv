from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRaisedButton, MDFillRoundFlatButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.clock import Clock
import requests
import sqlite3
import webbrowser

# --- Database ---
def init_db():
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved 
                      (id TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT)''')
    conn.commit()
    conn.close()

# --- UI Design (Material 3 inspirert) ---
KV = '''
MDScreen:
    md_bg_color: "#F8F9FA"

    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: "Pedagogisk Fagarkiv"
            elevation: 0
            md_bg_color: "#1A237E"
            right_action_items: [["bookmark", lambda x: app.show_saved()], ["history", lambda x: app.clear_results()]]

        MDScrollView:
            do_scroll_x: False
            
            MDBoxLayout:
                orientation: 'vertical'
                adaptive_height: True
                padding: [0, 0, 0, dp(20)]

                # Hero Seksjon med søk
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    md_bg_color: "#1A237E"
                    padding: [dp(20), dp(10), dp(20), dp(40)]
                    radius: [0, 0, dp(30), dp(30)]
                    spacing: dp(15)

                    MDLabel:
                        text: "Finn forskning for barnehagen"
                        theme_text_color: "Custom"
                        text_color: "#FFFFFF"
                        font_style: "H6"
                        halign: "center"

                    MDTextField:
                        id: search_input
                        hint_text: "Søk her..."
                        mode: "round"
                        fill_color_normal: "#FFFFFF"
                        on_text_validate: app.trigger_search()
                        pos_hint: {"center_x": .5}

                    MDFillRoundFlatButton:
                        id: search_button
                        text: "HENT ARTIKLER"
                        md_bg_color: "#FFAB40"
                        text_color: "#1A237E"
                        pos_hint: {"center_x": .5}
                        on_release: app.trigger_search()

                # Resultat-seksjon
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    padding: [dp(15), dp(20), dp(15), 0]
                    spacing: dp(15)

                    MDLabel:
                        id: info_label
                        text: "Klar for søk i OpenAlex og ERIC"
                        theme_text_color: "Hint"
                        font_style: "Caption"
                        halign: "center"

                    MDList:
                        id: results_list
                        spacing: dp(15)
'''

class PedagogiskApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        init_db()
        return Builder.load_string(KV)

    def trigger_search(self):
        query = self.root.ids.search_input.text.strip()
        if not query: return
        
        self.root.ids.search_button.disabled = True
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Kobler til arkiver..."
        
        # Bruker Clock for å unngå at UI fryser
        Clock.schedule_once(lambda dt: self.perform_multi_search(query), 0.2)

    def perform_multi_search(self, query):
        combined = []
        
        # 1. OpenAlex Søk
        try:
            oa_url = f"https://api.openalex.org/works?search={query}&per_page=10"
            oa_res = requests.get(oa_url, timeout=12)
            if oa_res.status_code == 200:
                for work in oa_res.json().get("results", []):
                    # Sikkerhetssjekk: Hopp over hvis tittel mangler
                    if not work.get("display_name"): continue
                    
                    combined.append({
                        'title': work.get("display_name"),
                        'year': work.get("publication_year") or "N/A",
                        'source': "OPENALEX",
                        'url': work.get("doi") or work.get("id") or "https://openalex.org"
                    })
        except Exception as e:
            print(f"OpenAlex error: {e}")

        # 2. ERIC Søk
        try:
            eric_url = f"https://api.ies.ed.gov/eric/?search={query}&format=json&rows=10"
            eric_res = requests.get(eric_url, timeout=12)
            if eric_res.status_code == 200:
                for doc in eric_res.json().get("response", {}).get("docs", []):
                    if not doc.get("title"): continue
                    
                    combined.append({
                        'title': doc.get("title"),
                        'year': doc.get("publicationdate") or "N/A",
                        'source': "ERIC",
                        'url': f"https://eric.ed.gov/?id={doc.get('id')}"
                    })
        except Exception as e:
            print(f"ERIC error: {e}")

        # Oppdater skjermen
        if combined:
            # Sorterer etter årstall (nyeste først)
            combined.sort(key=lambda x: str(x['year']), reverse=True)
            for item in combined:
                self.add_modern_card(item)
            self.root.ids.info_label.text = f"Fant {len(combined)} kilder"
        else:
            self.root.ids.info_label.text = "Ingen treff. Prøv andre ord."
            
        self.root.ids.search_button.disabled = False

    def add_modern_card(self, item):
        # Lager et visuelt pent kort for hver artikkel
        card = MDCard(
            orientation='vertical',
            padding=dp(15),
            size_hint=(1, None),
            height=dp(180),
            elevation=1,
            radius=[dp(16)],
            md_bg_color="#FFFFFF"
        )
        
        # Header med kilde og år
        header = MDBoxLayout(adaptive_height=True)
        header.add_widget(MDLabel(text=item['source'], font_style="Caption", theme_text_color="Secondary", bold=True))
        header.add_widget(MDLabel(text=str(item['year']), font_style="Caption", halign="right", theme_text_color="Hint"))
        card.add_widget(header)
        
        # Tittel (avkortet hvis for lang)
        title = item['title']
        if len(title) > 90: title = title[:87] + "..."
        card.add_widget(MDLabel(text=title, font_style="Subtitle1", bold=True, size_hint_y=None, height=dp(65)))
        
        # Knapperad
        actions = MDBoxLayout(adaptive_height=True, spacing=dp(10))
        actions.add_widget(MDFillRoundFlatButton(
            text="LES MER", font_size="12sp", md_bg_color="#1A237E",
            on_release=lambda x: webbrowser.open(item['url'])
        ))
        actions.add_widget(MDIconButton(
            icon="bookmark-plus-outline", theme_text_color="Custom", text_color="#1A237E",
            on_release=lambda x: self.save_to_db(item)
        ))
        
        card.add_widget(actions)
        self.root.ids.results_list.add_widget(card)

    def save_to_db(self, item):
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO saved VALUES (?, ?, ?, ?)", 
                           (str(item['url']), item['title'], item['source'], item['url']))
            conn.commit()
            self.root.ids.info_label.text = "Lagret i arkivet!"
        except:
            self.root.ids.info_label.text = "Allerede lagret."
        conn.close()

    def show_saved(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Ditt lagrede fagarkiv"
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            self.add_modern_card({'title': row[1], 'source': row[2], 'year': 'Arkiv', 'url': row[3]})

    def clear_results(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.search_input.text = ""
        self.root.ids.info_label.text = "Søk tømt"

if __name__ == "__main__":
    PedagogiskApp().run()
