import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
from polla_futbol import PollaFutbol
from dotenv import load_dotenv
import json
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import requests
import datetime
import pytz
from flask import current_app

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
    print(f"[LOG] /buscar-participante: id_polla={id_polla}, phone={phone}")
    if not id_polla or not phone:
        print("[LOG] /buscar-participante: Faltan parámetros")
        return jsonify({'error': 'Faltan parámetros'}), 400

    mongo_uri = os.getenv('MONGO_URI')
    print(f"[LOG] /buscar-participante: Conectando a MongoDB con URI: {mongo_uri}")
    client = MongoClient(mongo_uri, server_api=ServerApi('1'))
    db = client['pollafutbol']
    collection = db['participantes']

    print(f"[LOG] /buscar-participante: Buscando participante con id_polla={id_polla}, phone={phone}")
    participante = collection.find_one({'id_polla': int(id_polla), 'phone': phone})
    print(f"[LOG] /buscar-participante: Resultado de búsqueda: {participante}")
    if participante:
        participante.pop('_id', None)
        print(f"[LOG] /buscar-participante: Participante encontrado y retornado")
        return jsonify(participante)
    else:
        print(f"[LOG] /buscar-participante: Participante no encontrado")
        return jsonify(None), 200

def get_cached_partido_info():
    """Obtiene la info general del partido usando el caché de /partido-info."""
    cache_key = 'view//partido-info'
    data = cache.get(cache_key)
    if data is not None:
        print('[LOG] get_cached_partido_info: Usando datos cacheados')
        return data
    # Si no está en caché, llamar a la lógica de partido_info y guardar en caché
    print('[LOG] get_cached_partido_info: No hay datos en caché, obteniendo y cacheando')
    match_id_env = os.getenv('MATCH_ID')
    if not match_id_env:
        return None
    try:
        match_id = int(match_id_env)
    except ValueError:
        return None
    develop_mode = os.getenv('develop_mode', 'FALSE').upper() == 'TRUE'
    if develop_mode:
        try:
            with open('ejemplo_api_football.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[LOG] get_cached_partido_info: Error abriendo mock: {e}")
            return None
        if not data.get('response') or not data['response']:
            return None
        match = data['response'][0]
    else:
        polla = PollaFutbol()
        url = f"{polla.base_url}/fixtures"
        params = {'id': match_id}
        response = requests.get(url, headers=polla.headers, params=params)
        if response.status_code != 200:
            return None
        data = response.json()
        if not data.get('response') or not data['response']:
            return None
        match = data['response'][0]
    result = {
        'match_id': match_id,
        'id_polla': os.getenv('ID_POLLA'),
        'fixture': match.get('fixture', {}),
        'league': match.get('league', {}),
        'teams': match.get('teams', {})
    }
    cache.set(cache_key, result, timeout=86400)
    return result

def puede_registrar_o_actualizar():
    """Valida si se puede registrar/actualizar según la fecha del partido."""
    partido_info = get_cached_partido_info()
    if not partido_info:
        return False, 'No se pudo obtener la información del partido para validar el tiempo.'
    fixture = partido_info.get('fixture', {})
    fecha_partido_str = fixture.get('date')
    timezone = fixture.get('timezone', 'UTC')
    if not fecha_partido_str:
        return False, 'No se encontró la fecha del partido'
    # Parsear fecha del partido en UTC
    fecha_partido = datetime.datetime.fromisoformat(fecha_partido_str.replace('Z', '+00:00'))
    fecha_partido_utc = fecha_partido.astimezone(pytz.UTC)
    ahora_utc = datetime.datetime.now(pytz.UTC)
    diferencia = (fecha_partido_utc - ahora_utc).total_seconds() / 60  # minutos
    print(f"[LOG] Validación de tiempo: ahora_utc={ahora_utc}, fecha_partido_utc={fecha_partido_utc}, diferencia_minutos={diferencia}")
    if diferencia <= 5:
        return False, '¡El tiempo para registrar o modificar tu predicción ha terminado! Solo puedes hacerlo hasta 5 minutos antes del inicio del partido.'
    return True, None

@app.route('/actualizar-participante', methods=['PUT'])
def actualizar_participante():
    data = request.get_json()
    id_polla = data.get('id_polla')
    phone = data.get('phone')
    print(f"[LOG] /actualizar-participante: Datos recibidos: {data}")
    if not id_polla or not phone:
        print("[LOG] /actualizar-participante: Faltan parámetros")
        return jsonify({'error': 'Faltan parámetros'}), 400
    # Validar tiempo
    ok, msg = puede_registrar_o_actualizar()
    if not ok:
        print(f"[LOG] /actualizar-participante: Actualización bloqueada por tiempo: {msg}")
        return jsonify({'error': msg}), 403
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
    print(f"[LOG] /crear-participante: Datos recibidos: {data}")
    # Validar tiempo
    ok, msg = puede_registrar_o_actualizar()
    if not ok:
        print(f"[LOG] /crear-participante: Registro bloqueado por tiempo: {msg}")
        return jsonify({'error': msg}), 403
    # Validar campos requeridos
    required_fields = ['id_polla', 'name', 'phone', 'winner', 'first_half_score', 'second_half_score']
    for field in required_fields:
        if field not in data:
            print(f"[LOG] /crear-participante: Falta el campo requerido: {field}")
            return jsonify({'error': f'Falta el campo requerido: {field}'}), 400

    mongo_uri = os.getenv('MONGO_URI')
    print(f"[LOG] /crear-participante: Conectando a MongoDB con URI: {mongo_uri}")
    client = MongoClient(mongo_uri, server_api=ServerApi('1'))
    db = client['pollafutbol']
    collection = db['participantes']

    # Verificar si ya existe un participante con el mismo teléfono para esta polla
    print(f"[LOG] /crear-participante: Buscando si ya existe participante con id_polla={data['id_polla']}, phone={data['phone']}")
    existing = collection.find_one({
        'id_polla': int(data['id_polla']),
        'phone': data['phone']
    })
    print(f"[LOG] /crear-participante: Resultado de búsqueda existente: {existing}")
    if existing:
        print(f"[LOG] /crear-participante: Ya existe un participante con este teléfono para esta polla")
        return jsonify({'error': 'Ya existe un participante con este teléfono para esta polla'}), 409

    # Crear el nuevo participante
    try:
        print(f"[LOG] /crear-participante: Insertando nuevo participante en la base de datos")
        result = collection.insert_one({
            'id_polla': int(data['id_polla']),
            'name': data['name'],
            'phone': data['phone'],
            'winner': data['winner'],
            'first_half_score': data['first_half_score'],
            'second_half_score': data['second_half_score']
        })
        print(f"[LOG] /crear-participante: Resultado de insert_one: {result.inserted_id}")
        if result.inserted_id:
            print(f"[LOG] /crear-participante: Participante creado exitosamente")
            return jsonify({
                'success': True,
                'message': 'Participante creado exitosamente',
                'id': str(result.inserted_id)
            }), 201
        else:
            print(f"[LOG] /crear-participante: No se pudo crear el participante")
            return jsonify({'error': 'No se pudo crear el participante'}), 500
    except Exception as e:
        print(f"[LOG] Error creando participante: {e}")
        return jsonify({'error': 'Error al crear el participante'}), 500

@app.route('/partido-info', methods=['GET'])
def partido_info():
    data = get_cached_partido_info()
    if not data:
        return jsonify({'error': 'No se pudo obtener la información del partido'}), 500
    return jsonify(data)

@app.route('/participantes', methods=['GET'])
@cache.cached(timeout=300)  # 5 minutos
def participantes():
    id_polla_env = os.getenv('ID_POLLA')
    if not id_polla_env:
        return jsonify({'error': 'No se ha definido ID_POLLA en el entorno'}), 400
    try:
        id_polla = int(id_polla_env)
    except ValueError:
        return jsonify({'error': 'ID_POLLA debe ser un número entero'}), 400

    mongo_uri = os.getenv('MONGO_URI')
    print(f"[LOG] /participantes: Conectando a MongoDB con URI: {mongo_uri}")
    client = MongoClient(mongo_uri, server_api=ServerApi('1'))
    db = client['pollafutbol']
    collection = db['participantes']

    print(f"[LOG] /participantes: Buscando todos los participantes con id_polla={id_polla}")
    participantes = list(collection.find(
        {'id_polla': id_polla},
        {'_id': 0, 'name': 1, 'phone': 1, 'winner': 1, 'first_half_score': 1, 'second_half_score': 1}
    ))
    print(f"[LOG] /participantes: Encontrados {len(participantes)} participantes")
    return jsonify(participantes)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))