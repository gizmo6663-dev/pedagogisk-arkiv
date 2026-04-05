from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRaisedButton, MDFillRoundFlatButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.clock import Clock
from kivy.core.window import Window
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

# --- UI Design (KV-språk) ---
KV = '''
MDScreen:
    md_bg_color: "#F8F9FA"

    MDBoxLayout:
        orientation: 'vertical'

        # --- Toppmeny ---
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

                # --- Søke-seksjon (Hero) ---
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    md_bg_color: "#1A237E"
                    padding: [dp(20), dp(10), dp(20), dp(40)]
                    radius: [0, 0, dp(30), dp(30)]
                    spacing: dp(15)

                    MDLabel:
                        text: "Finn ny kunnskap for din barnehagehverdag"
                        theme_text_color: "Custom"
                        text_color: "#FFFFFF"
                        font_style: "H6"
                        halign: "center"

                    MDTextField:
                        id: search_input
                        hint_text: "Søk i faglitteratur..."
                        mode: "round"
                        fill_color_normal: "#FFFFFF"
                        hint_text_color_normal: "#757575"
                        on_text_validate: app.trigger_search()
                        pos_hint: {"center_x": .5}

                    MDFillRoundFlatButton:
                        id: search_button
                        text: "HENT FAGLITTERATUR"
                        md_bg_color: "#FFAB40"  # Kontrastfarge (Rav)
                        text_color: "#1A237E"
                        font_style: "Button"
                        pos_hint: {"center_x": .5}
                        on_release: app.trigger_search()

                # --- Info og Resultatliste ---
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    padding: [dp(15), dp(20), dp(15), 0]
                    spacing: dp(15)

                    MDLabel:
                        id: info_label
                        text: "Klar for profesjonelt søk"
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
        self.theme_cls.theme_style = "Light"
        init_db()
        return Builder.load_string(KV)

    def trigger_search(self):
        query = self.root.ids.search_input.text.strip()
        if not query: return
        
        self.root.ids.search_button.disabled = True
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Søker tverrfaglig..."
        
        Clock.schedule_once(lambda dt: self.perform_multi_search(query), 0.2)

    def perform_multi_search(self, query):
        combined = []
        
        # 1. OpenAlex
        try:
            oa_url = f"https://api.openalex.org/works?search={query}&per_page=8"
            oa_data = requests.get(oa_url, timeout=10).json()
            for work in oa_data.get("results", []):
                combined.append({
                    'title': work.get("display_name"),
                    'year': work.get("publication_year"),
                    'source': "OPENALEX (Global)",
                    'url': work.get("doi") or work.get("id"),
                    'color': "#E8EAF6"
                })
        except: pass

        # 2. ERIC
        try:
            eric_url = f"https://api.ies.ed.gov/eric/?search={query}&format=json&rows=8"
            eric_data = requests.get(eric_url, timeout=10).json()
            for doc in eric_data.get("response", {}).get("docs", []):
                combined.append({
                    'title': doc.get("title"),
                    'year': doc.get("publicationdate") or "N/A",
                    'source': "ERIC (Pedagogikk)",
                    'url': f"https://eric.ed.gov/?id={doc.get('id')}",
                    'color': "#F1F8E9"
                })
        except: pass

        if combined:
            combined.sort(key=lambda x: str(x['year']), reverse=True)
            for item in combined:
                self.add_modern_card(item)
            self.root.ids.info_label.text = f"Fant {len(combined)} relevante kilder"
        else:
            self.root.ids.info_label.text = "Ingen treff. Prøv andre nøkkelord."
            
        self.root.ids.search_button.disabled = False

    def add_modern_card(self, item):
        # Lager et moderne kort med avrundede hjørner og bedre spacing
        card = MDCard(
            orientation='vertical',
            padding=dp(15),
            size_hint=(1, None),
            height=dp(180),
            elevation=1,
            radius=[dp(16), dp(16), dp(16), dp(16)],
            md_bg_color="#FFFFFF",
            line_color=(0.1, 0.1, 0.1, 0.05)
        )
        
        # Innhold i kortet
        header = MDBoxLayout(adaptive_height=True, spacing=dp(10))
        header.add_widget(MDLabel(
            text=f"{item['source']}",
            font_style="Caption",
            theme_text_color="Secondary",
            bold=True
        ))
        header.add_widget(MDLabel(
            text=f"{item['year']}",
            font_style="Caption",
            halign="right",
            theme_text_color="Hint"
        ))
        
        card.add_widget(header)
        
        title_text = item['title']
        if len(title_text) > 90: title_text = title_text[:87] + "..."
            
        card.add_widget(MDLabel(
            text=title_text,
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            height=dp(60)
        ))
        
        # Knapperad
        actions = MDBoxLayout(adaptive_height=True, spacing=dp(10), padding=[0, dp(10), 0, 0])
        
        actions.add_widget(MDFillRoundFlatButton(
            text="LES ARTIKKEL",
            font_size="12sp",
            md_bg_color="#1A237E",
            on_release=lambda x: webbrowser.open(item['url'])
        ))
        
        actions.add_widget(MDIconButton(
            icon="bookmark-plus-outline",
            user_font_size="24sp",
            theme_text_color="Custom",
            text_color="#1A237E",
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
            self.root.ids.info_label.text = "Artikkel lagret!"
        except:
            self.root.ids.info_label.text = "Allerede lagret."
        conn.close()

    def show_saved(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Ditt personlige fagarkiv"
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
