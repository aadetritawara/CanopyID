import os
import pytest
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor
from moto import mock_aws


# Define global configurations
@pytest.fixture(scope="session")
def global_config():
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")

    return {
        "db_url": f"postgresql://{user}:{password}@localhost/{db}",
        "bucket_name": "local-test-bucket",
        "aws_region": "us-east-1",
    }


# Define test setup
@pytest.fixture(autouse=True)
def setup_infrastructure(global_config):
    # Inject variables into OS environment
    os.environ["DATABASE_URL"] = global_config["db_url"]
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["AWS_DEFAULT_REGION"] = global_config["aws_region"]

    # Wipe the tables before each test to ensure a clean slate
    conn = psycopg2.connect(global_config["db_url"], cursor_factory=RealDictCursor)
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM birds;")
        cursor.execute("DELETE FROM jobs;")
    conn.commit()
    conn.close()

    yield

@pytest.mark.parametrize(
    "audio_file_path, s3_file_key, job_id, expected_min_birds",
    [
        # single bird audio file 
        ("tests/test_assets/SongSparrow.mp3", "1.mp3", 1, 1),
        
        # 2 bird audio file
        ("tests/test_assets/TwoBirds.mp3", "2.mp3", 2, 2), 
    ]
)

@mock_aws
def test_lambda_audio_processing(
    global_config, 
    audio_file_path, 
    s3_file_key, 
    job_id, 
    expected_min_birds
):
    # setup mock S3 bucket & upload file
    s3_client = boto3.client("s3", region_name=global_config["aws_region"])
    s3_client.create_bucket(Bucket=global_config["bucket_name"])

    with open(audio_file_path, "rb") as audio_file:
        s3_client.put_object(
            Bucket=global_config["bucket_name"],
            Key=s3_file_key,
            Body=audio_file.read(),
        )

    # setup the specific job row for this test iteration
    setup_conn = psycopg2.connect(global_config["db_url"])
    with setup_conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO jobs (id, status, s3_file_key, latitude, longitude, created_at)
            VALUES (%s, 'PENDING', %s, 49.2827, -123.1207, NOW());
            """,
            (job_id, s3_file_key)
        )
    setup_conn.commit()
    setup_conn.close()

    print(f"\n--- Executing Lambda for {s3_file_key} ---")
    from services.birdnet_processor.lambda_handler import lambda_handler

    mock_event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": global_config["bucket_name"]},
                    "object": {"key": s3_file_key},
                }
            }
        ]
    }

    # invoke lambda
    lambda_handler(mock_event, None)

    # verify that the bird classifications were inserted into the bird table and job status updated to CLASSIFIED
    verify_conn = psycopg2.connect(global_config["db_url"], cursor_factory=RealDictCursor)
    with verify_conn.cursor() as cursor:
        
        cursor.execute("SELECT status FROM jobs WHERE id = %s;", (job_id,))
        job = cursor.fetchone()
        assert job["status"] == "CLASSIFIED", f"Job status should update to CLASSIFIED"

        cursor.execute("SELECT * FROM birds WHERE job_id = %s;", (job_id,))
        birds = cursor.fetchall()
        assert len(birds) >= expected_min_birds, f"Expected at least {expected_min_birds} birds, found {len(birds)}"

    verify_conn.close()