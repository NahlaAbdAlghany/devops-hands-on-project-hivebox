
    
from datetime import datetime, timedelta, timezone
import statistics
from flask import Flask, jsonify
import requests


app=Flask(__name__)

version='0.0.1'
def app_version():
    return (f"HiveBox Application Version: {version}"
)

SENSEBOX_API_URL = "https://api.opensensemap.org"    

#endpoint return version
@app.route('/version', methods=['GET'])
def getVersion():
    return app_version()


@app.route('/temperature', methods=['GET'])
def get_average_temperature():
    try:
        # Calculate timestamp for 1 hour ago
        one_hour_ago = datetime.now(timezone.utc)- timedelta(hours=1)
        timestamp_str = one_hour_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Get all senseBoxes with temperature sensors
        boxes_response = requests.get(
            f"{SENSEBOX_API_URL}/boxes",
            params={
                'phenomenon': 'temperature',
                'format': 'json'
            },
            timeout=10
        )
        
        if boxes_response.status_code != 200:
            return jsonify({
                'error': 'Failed to fetch senseBox data',
                'status_code': boxes_response.status_code
            }), 500
        
        boxes = boxes_response.json()
        
        if not boxes:
            return jsonify({
                'error': 'No senseBoxes found with temperature sensors'
            }), 404
        
        temperature_readings = []
        
        # Fetch recent temperature data for each box
        for box in boxes:
            box_id = box.get('_id')
            if not box_id:
                continue
                
            # Find temperature sensor ID
            sensors = box.get('sensors', [])
            temp_sensor_id = None
            
            for sensor in sensors:
                if sensor.get('phenomenon', '').lower() == 'temperature':
                    temp_sensor_id = sensor.get('_id')
                    break
            
            if not temp_sensor_id:
                continue
            
            try:
                # Get recent measurements for this sensor
                measurements_response = requests.get(
                    f"{SENSEBOX_API_URL}/boxes/{box_id}/sensors/{temp_sensor_id}/measurements",
                    params={
                        'from-date': timestamp_str,
                        'format': 'json'
                    },
                    timeout=5
                )
                
                if measurements_response.status_code == 200:
                    measurements = measurements_response.json()
                    
                    # Filter measurements from the last hour and extract valid temperature values
                    for measurement in measurements:
                        try:
                            # Parse measurement timestamp
                            measurement_time = datetime.fromisoformat(
                                measurement.get('createdAt', '').replace('Z', '+00:00')
                            )
                            
                            if measurement_time >= one_hour_ago:
                                temp_value = float(measurement.get('value', 0))

                                if -50 <= temp_value <= 60:
                                    temperature_readings.append(temp_value)
                        except (ValueError, TypeError):
                            continue
                            
            except requests.exceptions.RequestException:
                continue
        
        # Calculate average temperature
        if not temperature_readings:
            return jsonify({
                'error': 'No recent temperature data found (within last hour)',
                'average_temperature': None,
                'data_points': 0,
                'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
            }), 404
        
        average_temp = statistics.mean(temperature_readings)
        
        return jsonify({
            'average_temperature': round(average_temp, 2),
            'unit': '°C',
            'data_points': len(temperature_readings),
            'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
            'data_age_limit': '1 hour'
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': 'Failed to connect to senseBox API',
            'details': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9999, debug=True)
   