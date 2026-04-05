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
                      (id TEXT PRIMARY KEY, title TEXT, abstract TEXT, url TEXT)''')
    conn.commit()
    conn.close()

# --- Brukergrensesnitt (KV) ---
KV = '''
MDBoxLayout:
    orientation: 'vertical'
    md_bg_color: "#F8F9FA"

    MDTopAppBar:
        title: "Pedagogisk Arkiv (OpenAlex)"
        elevation: 4
        md_bg_color: "#1A237E"
        right_action_items: [["bookmark", lambda x: app.show_saved()], ["refresh", lambda x: app.clear_results()]]

    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(15)
        spacing: dp(10)

        MDTextField:
            id: search_input
            hint_text: "Søk i faglitteratur..."
            helper_text: "F.eks. 'Reggio Emilia', 'Inkludering', 'Lek'"
            helper_text_mode: "on_focus"
            mode: "rectangle"
            on_text_validate: app.search_articles()

        MDLabel:
            id: info_label
            text: "Klar for søk i OpenAlex-databasen"
            theme_text_color: "Hint"
            font_style: "Caption"
            halign: "center"
            size_hint_y: None
            height: dp(20)

        MDRaisedButton:
            id: search_button
            text: "START AKADEMISK SØK"
            md_bg_color: "#1A237E"
            pos_hint: {"center_x": .5}
            on_release: app.search_articles()

        MDScrollView:
            MDList:
                id: results_list
                spacing: dp(15)
'''

class PedagogiskApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        init_db()
        return Builder.load_string(KV)

    def search_articles(self):
        query = self.root.ids.search_input.text.strip()
        if not query: return
        
        # Deaktiver knapp og tøm liste
        self.root.ids.search_button.disabled = True
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Søker i 250 millioner artikler..."

        # OpenAlex Parametere
        # mailto-parameteren gjør at du havner i deres "Polite Pool" (raskere/færre feil)
        params = {
            'search': query,
            'mailto': 'din-epost@test.no',  # Legg gjerne inn din ekte e-post her
            'per_page': 15
        }

        try:
            url = "https://api.openalex.org/works"
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if results:
                    for work in results:
                        self.add_article_card(work)
                    self.root.ids.info_label.text = f"Fant {len(results)} relevante treff"
                else:
                    self.root.ids.info_label.text = "Ingen treff funnet."
            else:
                self.root.ids.info_label.text = f"Server-feil: {response.status_code}"
                
        except Exception as e:
            self.root.ids.info_label.text = "Tilkoblingsfeil. Sjekk internett."
        
        # Re-aktiver knappen etter en kort pause
        Clock.schedule_once(lambda dt: setattr(self.root.ids.search_button, 'disabled', False), 1)

    def add_article_card(self, work):
        # Henter data fra OpenAlex-formatet
        title = work.get("display_name", "Uten tittel")
        year = work.get("publication_year", "N/A")
        url = work.get("doi") or work.get("id") or "#"
        
        # OpenAlex lagrer abstracts i et komplisert format (Inverted Index).
        # For enkelhets skyld viser vi kilde/type her i stedet.
        source = work.get("primary_location", {}).get("source", {}).get("display_name", "Akademisk kilde")
        
        card = MDCard(
            orientation='vertical', 
            padding=15, 
            size_hint=(1, None), 
            height="180dp", 
            elevation=2, 
            radius=[12, 12, 12, 12],
            md_bg_color="#FFFFFF"
        )
        
        card.add_widget(MDLabel(
            text=f"{title} ({year})", 
            font_style="Subtitle1", 
            bold=True, 
            size_hint_y=None, 
            height="60dp"
        ))
        
        card.add_widget(MDLabel(
            text=f"Publisert i: {source}", 
            font_style="Caption", 
            theme_text_color="Secondary",
            size_hint_y=None, 
            height="30dp"
        ))
        
        actions = MDBoxLayout(adaptive_height=True, spacing=10, padding=[0, 10, 0, 0])
        
        # "LES"-knapp som åpner nettleseren
        actions.add_widget(MDRaisedButton(
            text="LES ARTIKKEL", 
            md_bg_color="#1A237E",
            on_release=lambda x: webbrowser.open(url)
        ))
        
        # Lagre-knapp
        actions.add_widget(MDIconButton(
            icon="bookmark-plus", 
            on_release=lambda x: self.save_to_db(work)
        ))
        
        card.add_widget(actions)
        self.root.ids.results_list.add_widget(card)

    def save_to_db(self, work):
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO saved VALUES (?, ?, ?, ?)", 
                           (work.get('id'), work.get('display_name'), "Lagret fra OpenAlex", work.get('doi')))
            conn.commit()
            self.root.ids.info_label.text = "Artikkel lagret i arkivet!"
        except:
            self.root.ids.info_label.text = "Allerede lagret."
        conn.close()

    def show_saved(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Ditt lagrede arkiv"
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            self.root.ids.results_list.add_widget(MDLabel(text="Ingen lagrede artikler ennå.", halign="center"))
        else:
            for row in rows:
                # Lager et enkelt objekt for å gjenbruke add_article_card
                fake_work = {
                    'display_name': row[1],
                    'publication_year': 'Arkivert',
                    'doi': row[3],
                    'id': row[0]
                }
                self.add_article_card(fake_work)

    def clear_results(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.search_input.text = ""
        self.root.ids.info_label.text = "Klar for nytt søk"

if __name__ == "__main__":
    PedagogiskApp().run()
