from flask import Flask, request, jsonify, Response
import requests, os, csv
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ✅ Allow only your Vercel frontend to access the backend
CORS(app, origins=["https://weather-app-8bji.vercel.app"])

# --- Supabase and API setup ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --- ✅ Default root route (Render homepage) ---
@app.route('/')
def home():
    return jsonify({"message": "Weather App Backend is running successfully!"}), 200


# --- 1️⃣ Fetch weather from OpenWeather + Save to Supabase ---
@app.route('/weather', methods=['GET'])
def get_weather():
    city = request.args.get('location')
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not city and not (lat and lon):
        return jsonify({"error": "Location (city) or coordinates (lat, lon) required"}), 400

    try:
        # ✅ Always use HTTPS
        if lat and lon:
            weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        else:
            weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"

        # Fetch data from OpenWeather
        weather_response = requests.get(weather_url, timeout=10).json()
        forecast_response = requests.get(forecast_url, timeout=10).json()

        # Safely extract fields
        temperature = weather_response.get("main", {}).get("temp", "N/A")
        description = weather_response.get("weather", [{}])[0].get("description", "N/A")
        humidity = weather_response.get("main", {}).get("humidity", "N/A")
        wind_speed = weather_response.get("wind", {}).get("speed", "N/A")
        city_name = weather_response.get("name") or city or f"{lat},{lon}"

        # Save to Supabase if data valid
        if temperature != "N/A":
            supabase.table("weather_requests").insert({
                "city": city_name,
                "temperature": temperature,
                "description": description,
                "humidity": humidity,
                "wind_speed": wind_speed
            }).execute()

        return jsonify({
            "city": city_name,
            "current": weather_response,
            "forecast": forecast_response
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 2️⃣ Retrieve all saved weather records from Supabase ---
@app.route('/history', methods=['GET'])
def get_history():
    try:
        response = supabase.table("weather_requests").select("*").order("created_at", desc=True).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 3️⃣ Add a new record manually (optional) ---
@app.route('/history', methods=['POST'])
def add_weather_record():
    try:
        data = request.json
        supabase.table("weather_requests").insert(data).execute()
        return jsonify({"message": "Record added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 4️⃣ Delete a record by ID ---
@app.route('/history/<int:record_id>', methods=['DELETE'])
def delete_weather_record(record_id):
    try:
        supabase.table("weather_requests").delete().eq("id", record_id).execute()
        return jsonify({"message": f"Record {record_id} deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 5️⃣ Export all weather history as CSV ---
@app.route('/export', methods=['GET'])
def export_csv():
    try:
        records = supabase.table("weather_requests").select("*").execute().data
        headers = ["id", "city", "temperature", "description", "humidity", "wind_speed", "created_at"]

        def generate():
            yield ",".join(headers) + "\n"
            for r in records:
                row = [str(r.get(h, "")) for h in headers]
                yield ",".join(row) + "\n"

        return Response(generate(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment;filename=weather_history.csv"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- ✅ Run app ---
if __name__ == '__main__':
    # Use host 0.0.0.0 and port 5000 for Render
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=False)