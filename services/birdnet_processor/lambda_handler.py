import sys
try:
    import ai_edge_litert as litert
    # creates a fake tflite_runtime module in memory
    # so when birdnetlib does 'import tflite_runtime', it gets LiteRT instead.
    sys.modules['tflite_runtime'] = litert
except ImportError:
    pass

import redis
import os
import boto3
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.parse
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from datetime import datetime

db_url = os.environ.get("DATABASE_URL") # lambda environment variable

r = redis.Redis(host=os.environ.get("REDIS_HOST"), port=6379, decode_responses=True)

# initialize database connection outside handler in case of warm starts
connection = None
try:
    print("Attempting to connect to RDS...")
    connection = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    print("Database connection successful.")
except Exception as e:
    print(f"Database connection failed: {e}")
    raise e

s3 = boto3.client('s3')

# Load and initialize the BirdNET-Analyzer models
print("Loading BirdNET Analyzer model...")
analyzer = Analyzer()
print("Model loaded.")

def lambda_handler(event, context): 
    
    global connection
    global r

    tmp_file_path = None

    # reconnect if connection dropped
    if connection.closed != 0:
        connection = psycopg2.connect(db_url, cursor_factory=RealDictCursor)

    # download audio file from s3 bucket
    try: 
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

        current_job_id = int(key.split('/')[-1].split('.')[0]) # assumes S3 key format is always "s3://<bucket>/<job_id>.wav"

        # download audio file to temporary storage
        tmp_file_path = f"/tmp/{key.split('/')[-1]}"
        print(f"Downloading s3://{bucket}/{key} to {tmp_file_path}")
        s3.download_file(bucket, key, tmp_file_path)

    except Exception as e:
        print(f"Error downloading object {key} from bucket {bucket}: {e}")
        raise e
    
    try:
        with connection.cursor() as cursor:
            
            select_query = """
                SELECT latitude, longitude, created_at
                FROM jobs
                WHERE id = %s;
            """

            cursor.execute(select_query, (current_job_id,))
            select_result = cursor.fetchone()

            if select_result is None:
                raise Exception(f"Job ID {current_job_id} not found in database.")

            # grab lat, lon, and date from database
            user_lat = select_result['latitude']
            user_lon = select_result['longitude']
            submitted_date = select_result['created_at']

            recording = Recording(
                analyzer,
                tmp_file_path,
                lat=user_lat,
                lon=user_lon,
                date=submitted_date,
                min_conf=0.25,
            )
            recording.analyze()
            print(f"Found {len(recording.detections)} detections.")

            insert_query = """
                INSERT INTO birds (job_id, bird_name, confidence_score, start_time, end_time) 
                VALUES (%s, %s, %s, %s, %s)
            """
            
            for detection in recording.detections:

                cursor.execute(insert_query, (
                    current_job_id, 
                    detection['common_name'], 
                    detection['confidence'], 
                    detection['start_time'], 
                    detection['end_time']
                ))

            connection.commit()
            print("Successfully saved all detections to RDS.")

            try:
                # publish to Redis stream for SSE updates
                r.publish(f"job:{current_job_id}", json.dumps({ 
                    "status": "classified",
                    "message": "Lambda Processing complete."
                 })) 
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                print("Redis connection lost. Reconnecting...")
                r = redis.Redis(host=os.environ.get("REDIS_HOST"), port=6379, decode_responses=True)

                # try publishing again after reconnecting
                r.publish(f"job:{current_job_id}", json.dumps({ 
                    "status": "classified",
                    "message": "Lambda Processing complete."
                 })) 

    except Exception as e:
        print(f"Error processing {key}: {e}")

        # roll back the transaction if anything fails to prevent partial data
        if connection:
            connection.rollback()

        raise e
    
    finally:
        # clean up the /tmp/ directory
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            print(f"Deleted temporary file {tmp_file_path}")