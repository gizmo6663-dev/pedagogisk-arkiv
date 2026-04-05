import os
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
import traceback
import certifi 

# --- SSL-KONFIGURASJON FOR ANDROID ---
# Dette er avgjørende for at appen ikke skal krasje ved internett-søk
os.environ['SSL_CERT_FILE'] = certifi.where()

def init_db():
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved 
                      (id TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT)''')
    conn.commit()
    conn.close()

# --- Design og Layout ---
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

                # Hero-seksjon (Blå bue)
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    md_bg_color: "#1A237E"
                    padding: [dp(20), dp(10), dp(20), dp(40)]
                    radius: [0, 0, dp(30), dp(30)]
                    spacing: dp(15)

                    MDLabel:
                        text: "Søk i verdens største forskningsarkiv"
                        theme_text_color: "Custom"
                        text_color: "#FFFFFF"
                        font_style: "H6"
                        halign: "center"

                    MDTextField:
                        id: search_input
                        hint_text: "Hva vil du lære mer om?"
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

                # Resultat-område
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    padding: [dp(15), dp(20), dp(15), 0]
                    spacing: dp(15)

                    MDLabel:
                        id: info_label
                        text: "Søker i OpenAlex"
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
        self.root.ids.info_label.text = "Kobler til arkivet..."
        
        # Bruker Clock for å holde UI flytende mens vi venter på svar
        Clock.schedule_once(lambda dt: self.perform_search(query), 0.2)

    def perform_search(self, query):
        results_to_show = []
        
        try:
            # Vi spør OpenAlex (15 treff per søk)
            oa_url = f"https://api.openalex.org/works?search={query}&per_page=15"
            response = requests.get(oa_url, timeout=12)
            
            if response.status_code == 200:
                data = response.json()
                for work in data.get("results", []):
                    # Sjekker at vi har en tittel før vi legger den til
                    if work.get("display_name"):
                        results_to_show.append({
                            'title': work.get("display_name"),
                            'year': work.get("publication_year") or "N/A",
                            'source': "OPENALEX",
                            'url': work.get("doi") or work.get("id") or "https://openalex.org"
                        })
                
                if results_to_show:
                    # Sorterer etter årstall (nyeste først)
                    results_to_show.sort(key=lambda x: str(x['year']), reverse=True)
                    for item in results_to_show:
                        self.add_modern_card(item)
                    self.root.ids.info_label.text = f"Fant {len(results_to_show)} kilder"
                else:
                    self.root.ids.info_label.text = "Ingen treff. Prøv et annet ord."
            else:
                self.root.ids.info_label.text = f"Feil fra server: {response.status_code}"
                
        except Exception:
            # Fanger feilen og viser en brukervennlig melding i stedet for krasj
            print(traceback.format_exc())
            self.root.ids.info_label.text = "Kunne ikke koble til. Sjekk nettet."
            
        self.root.ids.search_button.disabled = False

    def add_modern_card(self, item):
        # Lager et stilrent kort for hver artikkel
        card = MDCard(
            orientation='vertical',
            padding=dp(15),
            size_hint=(1, None),
            height=dp(170),
            elevation=1,
            radius=[dp(16)],
            md_bg_color="#FFFFFF"
        )
        
        # Topplinje med kilde og år
        header = MDBoxLayout(adaptive_height=True)
        header.add_widget(MDLabel(text=item['source'], font_style="Caption", theme_text_color="Secondary", bold=True))
        header.add_widget(MDLabel(text=str(item['year']), font_style="Caption", halign="right", theme_text_color="Hint"))
        card.add_widget(header)
        
        # Tittel
        display_title = item['title']
        if len(display_title) > 85: display_title = display_title[:82] + "..."
        card.add_widget(MDLabel(text=display_title, font_style="Subtitle1", bold=True, size_hint_y=None, height=dp(60)))
        
        # Knapper
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
            self.root.ids.info_label.text = "Lagret i ditt arkiv!"
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
