import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
from polla_futbol import PollaFutbol
from dotenv import load_dotenv
import json
from pymongo import MongoClient
from pymongo.server_api import ServerApi

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
    print(f"[LOG] MATCH_ID usado: {match_id}")
    match_data = get_match_data_with_log(match_id)
    print(f"[LOG] match_data recibido: {match_data}")
    
    if not match_data:
        print("[LOG] No se pudo obtener la información del partido (match_data es None o vacío)")
        return jsonify({
            "error": "No se pudo obtener la información del partido. Intente nuevamente en unos minutos."
        }), 503

    polla = PollaFutbol(id_polla=int(os.getenv('ID_POLLA', 1)))
    results = polla.process_match(match_id, match_data=match_data)
    print(f"[LOG] results calculados: {results}")

    if not results:
        print("[LOG] No se encontraron predicciones para este partido (results es None o vacío)")
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
    develop_mode = os.getenv('develop_mode', 'FALSE').upper() == 'TRUE'
    print(f"[LOG] get_match_data_with_log: develop_mode={develop_mode}, match_id={match_id}")
    if not develop_mode:
        api_call_count += 1
        print(f"[LOG] Llamada a la API de football número: {api_call_count}")
    polla = PollaFutbol()
    return polla.get_match_details(match_id)

@app.route('/buscar-participante', methods=['GET'])
def buscar_participante():
    id_polla = request.args.get('id_polla')
    phone = request.args.get('phone')
    if not id_polla or not phone:
        return jsonify({'error': 'Faltan parámetros'}), 400

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, server_api=ServerApi('1'))
    db = client['pollafutbol']
    collection = db['participantes']

    participante = collection.find_one({'id_polla': int(id_polla), 'phone': phone})
    if participante:
        participante.pop('_id', None)
        return jsonify(participante)
    else:
        return jsonify(None), 200

@app.route('/actualizar-participante', methods=['PUT'])
def actualizar_participante():
    data = request.get_json()
    id_polla = data.get('id_polla')
    phone = data.get('phone')
    if not id_polla or not phone:
        return jsonify({'error': 'Faltan parámetros'}), 400

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, server_api=ServerApi('1'))
    db = client['pollafutbol']
    collection = db['participantes']

    # Ignorar final_score al actualizar
    update_fields = {k: v for k, v in data.items() if k not in ['id_polla', 'phone', 'final_score']}
    result = collection.update_one(
        {'id_polla': int(id_polla), 'phone': phone},
        {'$set': update_fields}
    )
    if result.matched_count:
        return jsonify({'success': True, 'updated': result.modified_count})
    else:
        return jsonify({'error': 'Participante no encontrado'}), 404

@app.route('/crear-participante', methods=['POST'])
def crear_participante():
    data = request.get_json()
    
    # Validar campos requeridos
    required_fields = ['id_polla', 'name', 'phone', 'winner', 'first_half_score', 'second_half_score']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Falta el campo requerido: {field}'}), 400

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, server_api=ServerApi('1'))
    db = client['pollafutbol']
    collection = db['participantes']

    # Verificar si ya existe un participante con el mismo teléfono para esta polla
    existing = collection.find_one({
        'id_polla': int(data['id_polla']),
        'phone': data['phone']
    })
    if existing:
        return jsonify({'error': 'Ya existe un participante con este teléfono para esta polla'}), 409

    # Crear el nuevo participante
    try:
        result = collection.insert_one({
            'id_polla': int(data['id_polla']),
            'name': data['name'],
            'phone': data['phone'],
            'winner': data['winner'],
            'first_half_score': data['first_half_score'],
            'second_half_score': data['second_half_score']
        })
        
        if result.inserted_id:
            return jsonify({
                'success': True,
                'message': 'Participante creado exitosamente',
                'id': str(result.inserted_id)
            }), 201
        else:
            return jsonify({'error': 'No se pudo crear el participante'}), 500
            
    except Exception as e:
        print(f"[LOG] Error creando participante: {e}")
        return jsonify({'error': 'Error al crear el participante'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))