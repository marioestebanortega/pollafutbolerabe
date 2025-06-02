import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def buscar_partido_por_fecha(fecha, team1, team2):
    api_key = os.getenv('FOOTBALL_API_KEY')
    base_url = 'https://v3.football.api-sports.io'
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }

    url = f"{base_url}/fixtures"
    params = {
        'date': fecha  # formato: 'YYYY-MM-DD'
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if not data['response']:
            print("No se encontraron partidos para esa fecha")
            return

        print(f"\nPartidos encontrados el {fecha}:")
        for match in data['response']:
            home_team = match['teams']['home']['name']
            away_team = match['teams']['away']['name']
            match_id = match['fixture']['id']
            print(f"ID: {match_id} | {home_team} vs {away_team}")
            if (team1.lower() in home_team.lower() and team2.lower() in away_team.lower()) or \
               (team2.lower() in home_team.lower() and team1.lower() in away_team.lower()):
                print(f"--> ¡Este es el partido que buscas! ID: {match_id}")

    except requests.exceptions.RequestException as e:
        print(f"Error al buscar el partido: {e}")

if __name__ == "__main__":
    fecha = input("Ingresa la fecha (YYYY-MM-DD): ")
    buscar_partido_por_fecha(fecha, "Medellin", "America") 