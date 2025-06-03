import json
import os
import requests
from dotenv import load_dotenv
import pprint
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# Load environment variables
load_dotenv()

class PollaFutbol:
    def __init__(self, id_polla=None):
        self.api_key = os.getenv('FOOTBALL_API_KEY')
        self.base_url = 'https://v3.football.api-sports.io'
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        self.id_polla = id_polla
        self.participants = self.load_participants_from_mongo()

    def load_participants_from_mongo(self):
        mongo_uri = os.getenv('MONGO_URI')
        client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        db = client['pollafutbol']
        collection = db['participantes']
        query = {}
        if self.id_polla is not None:
            query['id_polla'] = self.id_polla
        print(f"[LOG] Query a MongoDB: {query}")
        participants = []
        for doc in collection.find(query):
            first_half = doc.get('first_half_score', '0-0')
            second_half = doc.get('second_half_score', '0-0')
            # Calcular marcador final sumando los tiempos
            try:
                first_home, first_away = map(int, first_half.split('-'))
                second_home, second_away = map(int, second_half.split('-'))
                final_home = first_home + second_home
                final_away = first_away + second_away
                final_score = f"{final_home}-{final_away}"
            except (ValueError, AttributeError):
                final_score = '0-0'
            participant = {
                'name': doc.get('name', ''),
                'winner': doc.get('winner', ''),
                'final_score': final_score,
                'first_half_score': first_half,
                'second_half_score': second_half
            }
            participants.append(participant)
        print(f"[LOG] Participantes encontrados: {len(participants)}")
        return participants

    def get_match_details(self, match_id):
        """Obtiene los detalles de un partido específico usando la API de football o un mock en modo desarrollo"""
        develop_mode_raw = os.getenv('develop_mode', 'FALSE')
        develop_mode = develop_mode_raw.upper() == 'TRUE'
        save_json_raw = os.getenv('SAVE_JSON', 'FALSE')
        save_json = save_json_raw.upper() == 'TRUE'
        print(f"[LOG] develop_mode (raw): '{develop_mode_raw}' interpretado como {develop_mode}")
        print(f"[LOG] SAVE_JSON (raw): '{save_json_raw}' interpretado como {save_json}")
        if develop_mode:
            print('[LOG] MODO DESARROLLO ACTIVADO: Usando mock de la API')
            try:
                with open('ejemplo_api_football.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[LOG] Error abriendo ejemplo_api_football.json: {e}")
                return None
            if data['response']:
                match = data['response'][0]
                # Extraer datos del partido
                home_team = match['teams']['home']['name']
                away_team = match['teams']['away']['name']
                home_logo = match['teams']['home']['logo']
                away_logo = match['teams']['away']['logo']
                league_logo = match['league']['logo']
                
                # Obtener marcadores (adaptado para partido no iniciado)
                goals_home = match['goals']['home'] if match['goals']['home'] is not None else 0
                goals_away = match['goals']['away'] if match['goals']['away'] is not None else 0
                halftime_home = match['score']['halftime']['home'] if match['score']['halftime']['home'] is not None else 0
                halftime_away = match['score']['halftime']['away'] if match['score']['halftime']['away'] is not None else 0
                
                # Calcular marcador del segundo tiempo
                second_half_home = goals_home - halftime_home
                second_half_away = goals_away - halftime_away
                
                # Determinar ganador
                if match['fixture']['status']['short'] in ['NS', 'TBD', 'PST', 'CANC', 'SUSP', 'INT', 'ABD', 'AWD', 'WO']:
                    winner = 'pending'
                elif goals_home > goals_away:
                    winner = 'home'
                elif goals_home < goals_away:
                    winner = 'away'
                else:
                    winner = 'draw'
                
                return {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_logo': home_logo,
                    'away_logo': away_logo,
                    'league_logo': league_logo,
                    'final_score': f"{goals_home}-{goals_away}",
                    'first_half_score': f"{halftime_home}-{halftime_away}",
                    'second_half_score': f"{second_half_home}-{second_half_away}",
                    'winner': winner,
                    'venue': match['fixture']['venue'],
                    'status': match['fixture']['status']
                }
        else:
            print('[LOG] MODO PRODUCTIVO: Llamando a la API de football')
            url = f"{self.base_url}/fixtures"
            params = {
                'id': match_id
            }
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                data = response.json()
                # Guardar la respuesta cruda de la API solo si SAVE_JSON=TRUE
                if save_json:
                    try:
                        with open('api_football_response.json', 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        print(f"[LOG] Error guardando api_football_response.json: {e}")
                if data['response']:
                    match = data['response'][0]
                    # Extraer datos del partido
                    home_team = match['teams']['home']['name']
                    away_team = match['teams']['away']['name']
                    home_logo = match['teams']['home']['logo']
                    away_logo = match['teams']['away']['logo']
                    league_logo = match['league']['logo']
                    
                    # Obtener marcadores (adaptado para partido no iniciado)
                    goals_home = match['goals']['home'] if match['goals']['home'] is not None else 0
                    goals_away = match['goals']['away'] if match['goals']['away'] is not None else 0
                    halftime_home = match['score']['halftime']['home'] if match['score']['halftime']['home'] is not None else 0
                    halftime_away = match['score']['halftime']['away'] if match['score']['halftime']['away'] is not None else 0
                    
                    # Calcular marcador del segundo tiempo
                    second_half_home = goals_home - halftime_home
                    second_half_away = goals_away - halftime_away
                    
                    # Determinar ganador
                    if match['fixture']['status']['short'] in ['NS', 'TBD', 'PST', 'CANC', 'SUSP', 'INT', 'ABD', 'AWD', 'WO']:
                        winner = 'pending'
                    elif goals_home > goals_away:
                        winner = 'home'
                    elif goals_home < goals_away:
                        winner = 'away'
                    else:
                        winner = 'draw'
                    
                    return {
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_logo': home_logo,
                        'away_logo': away_logo,
                        'league_logo': league_logo,
                        'final_score': f"{goals_home}-{goals_away}",
                        'first_half_score': f"{halftime_home}-{halftime_away}",
                        'second_half_score': f"{second_half_home}-{second_half_away}",
                        'winner': winner,
                        'venue': match['fixture']['venue'],
                        'status': match['fixture']['status']
                    }
        return None

    def _determine_winner(self, match):
        """Determina el ganador del partido"""
        home_goals = match['goals']['home']
        away_goals = match['goals']['away']
        
        if home_goals > away_goals:
            return match['teams']['home']['name']
        elif away_goals > home_goals:
            return match['teams']['away']['name']
        else:
            return "Empate"

    def calculate_score(self, prediction, actual_result):
        """Calcula la puntuación basada en las predicciones"""
        score = 0

        # Normalizar ganador predicho
        pred_winner = prediction['winner'].strip().lower()
        real_winner = actual_result['winner'].strip().lower()
        if pred_winner in ['empate', 'draw']:
            pred_winner_norm = 'draw'
        elif pred_winner in ['local', actual_result['home_team'].strip().lower()]:
            pred_winner_norm = actual_result['home_team'].strip().lower()
        elif pred_winner in ['visitante', actual_result['away_team'].strip().lower()]:
            pred_winner_norm = actual_result['away_team'].strip().lower()
        else:
            pred_winner_norm = pred_winner

        # 1. Ganador
        if pred_winner_norm == real_winner:
            score += 3

        # 2. Marcador final (suma de tiempos)
        try:
            pred_final = prediction['final_score']
            real_final = actual_result['final_score']
            if pred_final == real_final:
                score += 5
        except Exception:
            pass

        # 3. Primer tiempo
        if prediction['first_half_score'] == actual_result['first_half_score']:
            score += 2

        # 4. Segundo tiempo
        if prediction['second_half_score'] == actual_result['second_half_score']:
            score += 2

        return score

    def process_match(self, match_id, match_data=None):
        """Procesa un partido y calcula las puntuaciones"""
        if match_data is None:
            print("[LOG] process_match: obteniendo match_data desde get_match_details")
            match_data = self.get_match_details(match_id)
        else:
            print("[LOG] process_match: usando match_data pasado como argumento")
        print(f"[LOG] match_data recibido en process_match: {match_data}")
        print(f"[LOG] Participantes recibidos en process_match: {self.participants}")
        if not match_data:
            print("[LOG] match_data es None o vacío en process_match")
            return
        
        print(f"\nResultados del partido {match_data['home_team']} vs {match_data['away_team']}:")
        print(f"Ganador: {match_data['winner']}")
        print(f"Marcador Final: {match_data['final_score']}")
        print(f"Primer Tiempo: {match_data['first_half_score']}")
        print(f"Segundo Tiempo: {match_data['second_half_score']}\n")
        
        results = []
        for participant in self.participants:
            print(f"[LOG] Procesando participante: {participant}")
            try:
                score = self.calculate_score(participant, match_data)
                print(f"[LOG] Score calculado: {score}")
            except Exception as e:
                print(f"[LOG] Error calculando score para {participant['name']}: {e}")
                score = 0
            results.append({
                'name': participant['name'],
                'score': score,
                'predictions': {
                    'winner': participant['winner'],
                    'final_score': participant['final_score'],
                    'first_half': participant['first_half_score'],
                    'second_half': participant['second_half_score']
                }
            })
        print(f"[LOG] results generados en process_match: {results}")
        return results

def main():
    polla = PollaFutbol()
    # Usar el ID del partido desde el .env
    match_id = int(os.getenv('MATCH_ID'))
    print(f"Usando ID de partido desde .env: {match_id}")
    results = polla.process_match(match_id)
    
    if results:
        print("\nResultados de la polla:")
        for result in sorted(results, key=lambda x: x['score'], reverse=True):
            print(f"\n{result['name']}: {result['score']} puntos")
            print(f"Predicciones:")
            print(f"- Ganador: {result['predictions']['winner']}")
            print(f"- Marcador Final: {result['predictions']['final_score']}")
            print(f"- Primer Tiempo: {result['predictions']['first_half']}")
            print(f"- Segundo Tiempo: {result['predictions']['second_half']}")

if __name__ == "__main__":
    main() 