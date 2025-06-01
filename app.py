import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_caching import Cache
from polla_futbol import PollaFutbol
from dotenv import load_dotenv

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
    api_call_count += 1
    print(f"[LOG] Llamada real a la API de football número: {api_call_count}")
    polla = PollaFutbol()
    return polla.get_match_details(match_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))