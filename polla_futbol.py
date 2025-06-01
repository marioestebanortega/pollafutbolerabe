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
            participants.append({
                'name': doc['name'],
                'winner': doc['winner'],
                'final_score': doc['final_score'],
                'first_half_score': doc['first_half_score'],
                'second_half_score': doc['second_half_score']
            })
        print(f"[LOG] Participantes encontrados: {len(participants)}")
        return participants

    def get_match_details(self, match_id):
        """Obtiene los detalles del partido desde la API"""
        url = f"{self.base_url}/fixtures"
        params = {'id': match_id}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            if not data['response']:
                print("No se encontró el partido")
                return None
                
            match = data['response'][0]

            # Manejo seguro de secondhalf
            second_half = match['score'].get('secondhalf')
            if second_half and second_half['home'] is not None and second_half['away'] is not None:
                second_half_score = f"{second_half['home']}-{second_half['away']}"
            else:
                second_half_score = "N/A"

            return {
                'home_team': match['teams']['home']['name'],
                'away_team': match['teams']['away']['name'],
                'home_logo': match['teams']['home']['logo'],
                'away_logo': match['teams']['away']['logo'],
                'league_logo': match['league']['logo'],
                'winner': self._determine_winner(match),
                'final_score': f"{match['goals']['home']}-{match['goals']['away']}",
                'first_half_score': f"{match['score']['halftime']['home']}-{match['score']['halftime']['away']}",
                'second_half_score': second_half_score
            }
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener datos del partido: {e}")
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

        # Mapear predicción de ganador a nombre real
        pred_winner = prediction['winner'].lower()
        if pred_winner == 'local':
            pred_winner_name = actual_result['home_team'].lower()
        elif pred_winner == 'visitante':
            pred_winner_name = actual_result['away_team'].lower()
        else:
            pred_winner_name = 'empate'

        # Puntos por ganador (3 puntos)
        if pred_winner_name == actual_result['winner'].lower():
            score += 3
        
        # Puntos por marcador final (5 puntos)
        if prediction['final_score'] == actual_result['final_score']:
            score += 5
        
        # Puntos por primer tiempo (2 puntos)
        if prediction['first_half_score'] == actual_result['first_half_score']:
            score += 2
        
        # Puntos por segundo tiempo (2 puntos)
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