import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_caching import Cache
from polla_futbol import PollaFutbol
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)
CORS(app)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})  # 5 minutos
api_call_count = 0

@app.route('/resultados', methods=['GET'])
@cache.cached()
def get_resultados():
    print("[LOG] Refrescando datos de /resultados (no cache)")
    match_id = int(os.getenv('MATCH_ID'))
    match_data = get_match_data_with_log(match_id)
    
    if not match_data:
        return jsonify({
            "error": "No se pudo obtener la información del partido. Intente nuevamente en unos minutos."
        }), 503

    polla = PollaFutbol()
    results = polla.process_match(match_id)

    # Si estamos en modo desarrollo y no hay resultados, crear un mock
    if results is None and os.getenv('develop_mode', 'false').lower() == 'true':
        print('[LOG] Creando resultados mock para modo desarrollo')
        results = [
            {
                "name": "Usuario 1",
                "score": 7,
                "predictions": {
                    "winner": "local",
                    "final_score": "2-1",
                    "first_half": "1-0",
                    "second_half": "1-1"
                }
            },
            {
                "name": "Usuario 2",
                "score": 5,
                "predictions": {
                    "winner": "empate",
                    "final_score": "1-1",
                    "first_half": "0-0",
                    "second_half": "1-1"
                }
            },
            {
                "name": "Usuario 3",
                "score": 3,
                "predictions": {
                    "winner": "visitante",
                    "final_score": "0-2",
                    "first_half": "0-1",
                    "second_half": "0-1"
                }
            }
        ]

    if not results:
        return jsonify({
            "error": "No se encontraron predicciones para este partido."
        }), 404

    equipos = {
        "home": {
            "name": match_data['home_team'],
            "logo": match_data.get('home_logo', None)
        },
        "away": {
            "name": match_data['away_team'],
            "logo": match_data.get('away_logo', None)
        },
        "league": {
            "logo": match_data.get('league_logo', None)
        }
    }

    resultados_ordenados = sorted(results, key=lambda x: x['score'], reverse=True)
    posicion = 1
    prev_score = None
    skip = 0
    for idx, res in enumerate(resultados_ordenados, 1):
        if prev_score is not None and res['score'] == prev_score:
            res['posicion'] = posicion
            skip += 1
        else:
            posicion = idx
            res['posicion'] = posicion
            skip = 1
        prev_score = res['score']

    response_data = {
        "equipos": equipos,
        "resultados": resultados_ordenados,
        "resultado_real": {
            "final_score": match_data['final_score'],
            "first_half_score": match_data['first_half_score'],
            "second_half_score": match_data['second_half_score'],
            "winner": match_data['winner']
        },
        "estadio": {
            "nombre": match_data.get('venue', {}).get('name', 'No disponible'),
            "ciudad": match_data.get('venue', {}).get('city', 'No disponible')
        },
        "status": {
            "estado": match_data.get('status', {}).get('long', 'No disponible'),
            "minutos": match_data.get('status', {}).get('elapsed', 0),
            "tiempo_extra": match_data.get('status', {}).get('extra', 0)
        }
    }
    return jsonify(response_data)

def get_match_data_with_log(match_id):
    global api_call_count
    develop_mode = os.getenv('develop_mode', 'false').lower() == 'true'
    if develop_mode:
        print('[LOG] MODO DESARROLLO ACTIVADO: Usando mock de la API')
        with open('ejemplo_api_football.json', 'r') as f:
            mock_data = json.load(f)
        # Tomar el primer elemento de response
        response = mock_data['response'][0]
        
        # Adaptar el formato del JSON de ejemplo al formato que espera el código
        adapted_data = {
            'home_team': response['teams']['home']['name'],
            'away_team': response['teams']['away']['name'],
            'home_logo': response['teams']['home']['logo'],
            'away_logo': response['teams']['away']['logo'],
            'league_logo': response['league']['logo'],
            'final_score': f"{response['goals']['home']}-{response['goals']['away']}",
            'first_half_score': f"{response['score']['halftime']['home']}-{response['score']['halftime']['away']}",
            'second_half_score': f"{response['goals']['home'] - response['score']['halftime']['home']}-{response['goals']['away'] - response['score']['halftime']['away']}",
            'winner': 'home' if response['goals']['home'] > response['goals']['away'] else 'away' if response['goals']['home'] < response['goals']['away'] else 'draw',
            'venue': response['fixture']['venue'],
            'status': response['fixture']['status']
        }
        return adapted_data
    else:
        api_call_count += 1
        print(f"[LOG] Llamada real a la API de football número: {api_call_count}")
        polla = PollaFutbol()
        return polla.get_match_details(match_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))