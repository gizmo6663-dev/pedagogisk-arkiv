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
import traceback # Trengs for å fange nøyaktig feil

def init_db():
    conn = sqlite3.connect("pedagogisk_arkiv.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved 
                      (id TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT)''')
    conn.commit()
    conn.close()

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
            MDBoxLayout:
                orientation: 'vertical'
                adaptive_height: True
                padding: [0, 0, 0, dp(20)]
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
                    MDFillRoundFlatButton:
                        id: search_button
                        text: "HENT ARTIKLER"
                        md_bg_color: "#FFAB40"
                        text_color: "#1A237E"
                        pos_hint: {"center_x": .5}
                        on_release: app.trigger_search()
                MDBoxLayout:
                    orientation: 'vertical'
                    adaptive_height: True
                    padding: [dp(15), dp(20), dp(15), 0]
                    spacing: dp(15)
                    MDLabel:
                        id: info_label
                        text: "Klar for søk"
                        theme_text_color: "Hint"
                        font_style: "Caption"
                        halign: "center"
                    MDList:
                        id: results_list
                        spacing: dp(15)
'''

class PedagogiskApp(MDApp):
    def build(self):
        init_db()
        return Builder.load_string(KV)

    def trigger_search(self):
        query = self.root.ids.search_input.text.strip()
        if not query: return
        self.root.ids.search_button.disabled = True
        self.root.ids.info_label.text = "Kobler til arkiver..."
        Clock.schedule_once(lambda dt: self.perform_multi_search(query), 0.2)

    def perform_multi_search(self, query):
        combined = []
        try:
            # --- Sjekk OpenAlex ---
            try:
                oa_res = requests.get(f"https://api.openalex.org/works?search={query}&per_page=8", timeout=10)
                if oa_res.status_code == 200:
                    for work in oa_res.json().get("results", []):
                        if work.get("display_name"):
                            combined.append({'title': work.get("display_name"), 'year': work.get("publication_year") or "N/A", 'source': "OPENALEX", 'url': work.get("doi") or work.get("id") or "https://openalex.org"})
            except Exception as e:
                print(f"OA Feil: {e}")

            # --- Sjekk ERIC ---
            try:
                eric_res = requests.get(f"https://api.ies.ed.gov/eric/?search={query}&format=json&rows=8", timeout=10)
                if eric_res.status_code == 200:
                    for doc in eric_res.json().get("response", {}).get("docs", []):
                        if doc.get("title"):
                            combined.append({'title': doc.get("title"), 'year': doc.get("publicationdate") or "N/A", 'source': "ERIC", 'url': f"https://eric.ed.gov/?id={doc.get('id')}"})
            except Exception as e:
                print(f"ERIC Feil: {e}")

            if combined:
                combined.sort(key=lambda x: str(x['year']), reverse=True)
                for item in combined:
                    self.add_card(item)
                self.root.ids.info_label.text = f"Fant {len(combined)} kilder"
            else:
                self.root.ids.info_label.text = "Ingen treff funnet."

        except Exception:
            # HVIS ALT GÅR GALT: Vis feilmeldingen på skjermen i stedet for å krasje
            error_msg = traceback.format_exc()
            self.root.ids.info_label.text = f"KRASJ-INFO: {error_msg[:50]}..."
            print(error_msg)
            
        self.root.ids.search_button.disabled = False

    def add_card(self, item):
        card = MDCard(orientation='vertical', padding=dp(15), size_hint=(1, None), height=dp(170), elevation=1, radius=[dp(16)], md_bg_color="#FFFFFF")
        title = item['title'][:85] + "..." if len(item['title']) > 88 else item['title']
        card.add_widget(MDLabel(text=f"{item['source']} | {item['year']}", font_style="Caption", theme_text_color="Secondary", bold=True))
        card.add_widget(MDLabel(text=title, font_style="Subtitle1", bold=True, size_hint_y=None, height=dp(60)))
        btn = MDFillRoundFlatButton(text="LES MER", font_size="12sp", md_bg_color="#1A237E", on_release=lambda x: webbrowser.open(item['url']))
        card.add_widget(btn)
        self.root.ids.results_list.add_widget(card)

    def save_to_db(self, item):
        # (Samme som før)
        pass

    def show_saved(self):
        # (Samme som før)
        pass

    def clear_results(self):
        self.root.ids.results_list.clear_widgets()
        self.root.ids.info_label.text = "Søk tømt"

if __name__ == "__main__":
    PedagogiskApp().run()
