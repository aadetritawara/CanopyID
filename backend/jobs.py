from sqlalchemy import select

import boto3
from fastapi import status
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request
from backend.schemas import JobCreateResponse, JobResponse, JobCreate
from backend.db.database import get_db
from backend.db.models import Job, Bird, Status
from backend.langChain import langchain_classification_summary
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import update
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as redis
import json

router = APIRouter()

r = redis.Redis(host="redis", port=6379, decode_responses=True)


async def get_classified_birds(
    job_id: int, db: AsyncSession
) -> list[dict]:
    """
    Helper function to query the Bird table for bird classifications related to a specific job_id.
    Called after the Lambda finishes classifying, to get the classifications to send to the frontend.
    """

    # query the Bird table for classifications related to this job_id
    query = select(
        Bird.bird_name, Bird.confidence_score, Bird.start_time, Bird.end_time
    ).where(Bird.job_id == job_id)
    birds = await db.execute(query)

    # update the Job status to summarizing
    update_query = update(Job).where(Job.id == job_id).values(status=Status.SUMMARIZING)

    await db.execute(update_query)
    await db.commit()

    return birds.mappings().all()  # convert rows into dicts


async def update_db_with_langchain_result(
    job_id: int, error: bool, result_profile: str, db: AsyncSession
) -> None:
    """Update the Job record with the generated LangChain profile summary or an error message."""
    if error:
        query = (
            update(Job)
            .where(Job.id == job_id)
            .values(status=Status.FAILED, result_profile=result_profile)
        )
    else:
        query = (
            update(Job)
            .where(Job.id == job_id)
            .values(status=Status.COMPLETED, result_profile=result_profile)
        )

    await db.execute(query)
    await db.commit()


async def job_event_generator(job_id: int, request, db: AsyncSession = Depends(get_db)):
    """
    Generate server-sent events for a given job_id by subscribing to a Redis channel.
    Yields events one at a time and streams each yield to the client.
    Function only exits when the job is done or the client disconnects.
    """
    pubsub = r.pubsub()
    # only continue once we've successfully subscribed to the Redis channel for this job_id
    await pubsub.subscribe(f"job:{job_id}")

    try:
        # upon connection, send a submission confirmation
        yield {
            "event": "submit_confirmation",
            "data": json.dumps(
                {
                    "status": "classifying",
                    "message": "Audio received! Classifying your birds...",
                }
            ),
        }

        async for message in pubsub.listen():
            # waiting for Redis messages

            # skipping subscription confirmation message sent by Redis on first subscribe, and any other non message types
            if message["type"] != "message":
                continue

            # check if the frontend disconnected (tab closed, etc.)
            if await request.is_disconnected():
                break

            payload = json.loads(message["data"])
            event_type = payload.get("status")

            if event_type == "classified":
                # lambda finished classifying, get classifications from bird db for this job_id
                classifications = await get_classified_birds(job_id, db)

                # sending bird classifications and sse update to frontend
                yield {
                    "event": "classified",
                    "data": json.dumps(
                        {
                            "status": "classified",
                            "message": "Bird(s) identified! Generating profile(s)...",
                            "classifications": classifications,
                        }
                    ),
                }

                # check if the frontend disconnected (tab closed, etc.)
                if await request.is_disconnected():
                    break

                # find common names of all classified birds
                unique_birds = set(
                    [classification["bird_name"] for classification in classifications]
                )

                # get additional context information (user's location, date of recording) from the Job table to feed into LangChain prompt
                query = select(Job.latitude, Job.longitude, Job.created_at).where(
                    Job.id == job_id
                )
                job_context_info = await db.execute(query).mappings().all()

                # call lang chain helper function with context info and unique birds to generate a summary profile of the birds in the recording
                classification_summary = await langchain_classification_summary(
                    unique_birds, job_context_info
                )

                # check if the summarized dictionary contains the 'error' key
                if "error" in classification_summary:
                    content = classification_summary["error"]
                    await update_db_with_langchain_result(job_id, error=True, result_profile=content, db=db)
                else:
                    content = ""
                    for bird, summary in classification_summary.items():
                        content += f"### {bird}\n{summary}\n\n"
                    await update_db_with_langchain_result(job_id, error=False, result_profile=content, db=db)

                # send the generated profile(s) back to the frontend as an sse update
                yield {
                        "event": "complete",
                        "data": json.dumps(
                            {
                                "status": "complete" if "error" not in classification_summary else "failed",
                                "result_profile": content
                            }
                        ),
                    }
                
                # break the loop since the task is finished
                break
    finally:
        # clean up the Redis subscription, even if client disconnects
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.close()


def get_presigned_url(job_id: int) -> str:
    """
    Generate a presigned S3 URL for the frontend to upload the audio file to.
    The S3 key is based on the job_id, so the Lambda can easily find it when triggered.
    """
    s3_client = boto3.client("s3")
    bucket_name = "canopy-id-bucket"
    object_key = f"{job_id}.wav"

    try:
        response = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket_name, "Key": object_key},
            ExpiresIn=3600,
        )
        return response
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        )


@router.get("/{job_id}/stream", response_class=EventSourceResponse)
async def stream_job(job_id: int, request: Request):
    """
    Endpoint for streaming server-sent events related to a specific job_id.
    The frontend will connect to this endpoint after creating a job and uploading the audio file,
    and will listen for updates on the job status, classifications, and final profile result.
    """
    return EventSourceResponse(job_event_generator(job_id, request))


@router.post("/", response_model=JobCreateResponse)
async def create_job(
    job: JobCreate,
    db: AsyncSession = Depends(
        get_db
    ),  # fresh db session for this request, automatically closed when done
):
    """
    Create a new job entry in the database with status PENDING, then return the job details along with a
    presigned S3 URL for the frontend to upload the audio file to.
    The S3 key is based on the job_id, so the Lambda can easily find it when triggered.
    """

    # create a new job entry in the database with status PENDING
    new_job = Job(status=Status.PENDING, latitude=job.latitude, longitude=job.longitude)

    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # get a presigned URL from S3 for the frontend to upload the audio file to, and return it in the response
    presigned_url = get_presigned_url(new_job.id)

    return {"job": new_job, "upload_url": presigned_url}
