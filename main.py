from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.clock import Clock
import requests
import sqlite3
import webbrowser

# --- Databaseoppsett ---
def init_db():
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved 
                      (id TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT)''')
    conn.commit()
    conn.close()

# --- Brukergrensesnitt (KV-språk) ---
KV = '''
MDBoxLayout:
    orientation: 'vertical'
    md_bg_color: "#F4F7F9"

    MDTopAppBar:
        title: "Pedagogisk Fagarkiv"
        elevation: 4
        md_bg_color: "#1A237E"
        right_action_items: [["bookmark", lambda x: app.show_saved()], ["refresh", lambda x: app.clear_results()]]

    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(15)
        spacing: dp(10)

        MDTextField:
            id: search_input
            hint_text: "Søk (f.eks. 'lek', 'utemiljø', 'didaktikk')"
            helper_text: "Søker i OpenAlex og ERIC"
            helper_text_mode: "on_focus"
            mode: "rectangle"
            on_text_validate: app.trigger_search()

        MDLabel:
            id: info_label
            text: "Klar for profesjonelt fagsøk"
            theme_text_color: "Hint"
            font_style: "Caption"
            halign: "center"
            size_hint_y: None
            height: dp(20)

        MDRaisedButton:
            id: search_button
            text: "HENT LITTERATUR"
            md_bg_color: "#1A237E"
            pos_hint: {"center_x": .5}
            on_release: app.trigger_search()

        MDScrollView:
            MDList:
                id: results_list
                spacing: dp(12)
'''

class PedagogiskApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        init_db()
        return Builder.load_string(KV)

    def trigger_search(self):
        query = self.root.ids.search_input.text.strip()
        if not query: return
        
        # Visuelt feedback
        self.root.ids.search_button.disabled = True
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Søker i faglitteraturen..."
        
        # Kjører selve søket
        Clock.schedule_once(lambda dt: self.perform_search(query), 0.2)

    def perform_search(self, query):
        combined_results = []
        
        # 1. SØK I OPENALEX (Global forskning)
        try:
            oa_url = f"https://api.openalex.org/works?search={query}&per_page=10"
            oa_data = requests.get(oa_url, timeout=10).json()
            for work in oa_data.get("results", []):
                combined_results.append({
                    'title': work.get("display_name"),
                    'year': work.get("publication_year"),
                    'source': "OpenAlex (Global)",
                    'url': work.get("doi") or work.get("id")
                })
        except:
            pass

        # 2. SØK I ERIC (Pedagogikk-spesialist)
        try:
            eric_url = f"https://api.ies.ed.gov/eric/?search={query}&format=json&rows=10"
            eric_data = requests.get(eric_url, timeout=10).json()
            for doc in eric_data.get("response", {}).get("docs", []):
                combined_results.append({
                    'title': doc.get("title"),
                    'year': doc.get("publicationdate") or "N/A",
                    'source': "ERIC (Utdanning)",
                    'url': f"https://eric.ed.gov/?id={doc.get('id')}"
                })
        except:
            pass

        # Oppdater UI med resultater
        if combined_results:
            # Sorterer slik at nyeste artikler kommer øverst
            combined_results.sort(key=lambda x: str(x['year']), reverse=True)
            for item in combined_results:
                self.add_article_card(item)
            self.root.ids.info_label.text = f"Fant {len(combined_results)} artikler"
        else:
            self.root.ids.info_label.text = "Ingen treff. Prøv bredere søkeord."
            
        self.root.ids.search_button.disabled = False

    def add_article_card(self, item):
        # Forkorter lange titler for bedre design
        display_title = item['title']
        if len(display_title) > 85:
            display_title = display_title[:82] + "..."
            
        card = MDCard(
            orientation='vertical', padding=15, size_hint=(1, None), 
            height="160dp", elevation=1, radius=[12], md_bg_color="#FFFFFF"
        )
        
        card.add_widget(MDLabel(
            text=display_title, font_style="Subtitle1", bold=True, 
            size_hint_y=None, height="60dp"
        ))
        
        card.add_widget(MDLabel(
            text=f"{item['source']} | {item['year']}", 
            font_style="Caption", theme_text_color="Secondary"
        ))
        
        actions = MDBoxLayout(adaptive_height=True, spacing=10, padding=[0, 10, 0, 0])
        
        actions.add_widget(MDRaisedButton(
            text="LES", md_bg_color="#1A237E",
            on_release=lambda x: webbrowser.open(item['url'])
        ))
        
        actions.add_widget(MDIconButton(
            icon="bookmark-outline", 
            on_release=lambda x: self.save_to_db(item)
        ))
        
        card.add_widget(actions)
        self.root.ids.results_list.add_widget(card)

    def save_to_db(self, item):
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        try:
            # Bruker URL som ID for å unngå duplikater
            cursor.execute("INSERT INTO saved VALUES (?, ?, ?, ?)", 
                           (str(item['url']), item['title'], item['source'], item['url']))
            conn.commit()
            self.root.ids.info_label.text = "Lagret i arkivet!"
        except:
            self.root.ids.info_label.text = "Allerede lagret."
        conn.close()

    def show_saved(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Ditt personlige arkiv"
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            self.root.ids.results_list.add_widget(MDLabel(text="Arkivet er tomt.", halign="center"))
        else:
            for row in rows:
                self.add_article_card({'title': row[1], 'source': row[2], 'year': 'Arkiv', 'url': row[3]})

    def clear_results(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.search_input.text = ""
        self.root.ids.info_label.text = "Klar for nytt søk"

if __name__ == "__main__":
    PedagogiskApp().run()
