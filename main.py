from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
import requests
import sqlite3
import webbrowser

# --- Database ---
def init_db():
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved 
                      (id TEXT PRIMARY KEY, title TEXT, abstract TEXT, url TEXT)''')
    conn.commit()
    conn.close()

# --- UI Design ---
KV = '''
MDBoxLayout:
    orientation: 'vertical'
    md_bg_color: "#F0F2F5"

    MDTopAppBar:
        title: "Pedagogisk Arkiv"
        elevation: 4
        md_bg_color: "#1A237E"
        right_action_items: [["bookmark", lambda x: app.show_saved()], ["refresh", lambda x: app.clear_results()]]

    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(15)
        spacing: dp(10)

        MDTextField:
            id: search_input
            hint_text: "Søk bredt i faglitteratur..."
            helper_text: "Psykologi, pedagogikk, etikk, sosiologi"
            helper_text_mode: "persistent"
            mode: "rectangle"
            on_text_validate: app.search_articles()
            line_color_focus: "#1A237E"

        MDLabel:
            id: info_label
            text: "Klar for tverrfaglig søk"
            theme_text_color: "Hint"
            font_style: "Caption"
            halign: "center"
            size_hint_y: None
            height: dp(20)

        MDRaisedButton:
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
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        init_db()
        return Builder.load_string(KV)

        def search_articles(self):
        query = self.root.ids.search_input.text.strip()
        if not query: return
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Søker tverrfaglig..."
        
        # Vi legger til en "User-Agent" header. Noen API-er blokkerer forespørsler
        # som ser ut som de kommer fra en "bot" (standard Python-requests).
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) PedagogiskArkiv/1.0'
        }
        
        broad_context = f"({query}) AND (child OR education OR psychology OR ethics)"

        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={broad_context}&limit=15&fields=title,abstract,url,year,fieldsOfStudy"
            
            # Vi legger til timeout og headers
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and data["data"]:
                    for paper in data["data"]:
                        self.add_article_card(paper)
                    self.root.ids.info_label.text = f"Fant {len(data['data'])} artikler"
                else:
                    self.root.ids.info_label.text = "Ingen treff. Prøv bredere ord."
            else:
                self.root.ids.info_label.text = f"API-feil: Status {response.status_code}"
                
        except requests.exceptions.SSLError:
            self.root.ids.info_label.text = "Sikkerhetsfeil (SSL). Sjekk dato/tid på tlf."
        except requests.exceptions.ConnectionError:
            self.root.ids.info_label.text = "Ingen internettforbindelse."
        except Exception as e:
            # Denne vil vise oss den nøyaktige feilkoden på skjermen
            self.root.ids.info_label.text = f"Feil: {str(e)[:30]}"


    def add_article_card(self, paper):
        title = paper.get("title", "Uten tittel")
        year = paper.get("year", "N/A")
        abstract = paper.get("abstract", "")
        fields = ", ".join(paper.get("fieldsOfStudy", [])) if paper.get("fieldsOfStudy") else "Generelt"
        url = paper.get("url", "#")
        
        card = MDCard(orientation='vertical', padding=15, size_hint=(1, None), height="220dp", elevation=2, radius=[10])
        card.add_widget(MDLabel(text=f"{title} ({year})", font_style="Subtitle1", bold=True, size_hint_y=None, height="50dp"))
        card.add_widget(MDLabel(text=f"Felt: {fields}", font_style="Caption", theme_text_color="Custom", text_color="#1A237E", size_hint_y=None, height="20dp"))
        card.add_widget(MDLabel(text=(abstract[:180] + "...") if abstract else "Klikk LES for info", font_style="Body2", theme_text_color="Secondary", italic=True))
        
        actions = MDBoxLayout(adaptive_height=True, spacing=10)
        actions.add_widget(MDRaisedButton(text="LES", md_bg_color="#1A237E", on_release=lambda x: webbrowser.open(url)))
        actions.add_widget(MDIconButton(icon="bookmark-plus", on_release=lambda x: self.save_to_db(paper)))
        card.add_widget(actions)
        self.root.ids.results_list.add_widget(card)

    def save_to_db(self, paper):
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO saved VALUES (?, ?, ?, ?)", (paper.get('paperId'), paper['title'], paper.get('abstract', ''), paper.get('url', '')))
            conn.commit()
        except: pass
        conn.close()

    def show_saved(self):
        self.root.ids.results_list.clear_widgets()
        conn = sqlite3.connect("pedagogisk_arkiv.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            self.add_article_card({"paperId": row[0], "title": row[1], "abstract": row[2], "url": row[3]})

    def clear_results(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.search_input.text = ""

if __name__ == "__main__":
    PedagogiskApp().run()

