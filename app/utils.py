import os
from sentence_transformers import SentenceTransformer
import boto3
from uuid import uuid4
from botocore.exceptions import BotoCoreError, ClientError

# ============== embedding model ===============
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    return embedding_model.encode(chunks).tolist()


# ================== s3 uploads =====================
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION,
)

async def upload_file_to_s3(user_id: str, file_data: bytes, original_filename: str, content_type: str):
    ext = os.path.splitext(original_filename)[1]
    unique_name = f"{uuid4()}{ext}"
    s3_key = f"documents/{user_id}/{unique_name}"

    try:
        s3_client.put_object(
            Bucket=AWS_BUCKET,
            Key=s3_key,
            Body=file_data,
            ContentType=content_type,
        )

        file_url = f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

        return {
            "s3_key": s3_key,
            "url": file_url,
            "filename": original_filename,
            "size": len(file_data),
            "content_type": content_type,
        }

    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"S3 upload failed: {str(e)}")
    
# ============= get presigned url ================
def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """
    Generate a pre-signed URL to access a private S3 file.

    :param key: Full S3 key/path of the file (e.g., 'documents/user_xxx/abc.pdf')
    :param expires_in: Expiry time in seconds (default 1 hour)
    :return: Pre-signed URL as a string
    """
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': AWS_BUCKET,
                'Key': key
            },
            ExpiresIn=expires_in
        )
        return url
    except ClientError as e:
        print(f"Failed to generate presigned URL: {e}")
        return None    