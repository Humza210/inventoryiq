# storage_s3.py
import os, mimetypes, uuid
import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET  = os.getenv("S3_BUCKET")
S3_PUBLIC  = os.getenv("S3_PUBLIC", "True").lower() == "true"

_s3 = boto3.client("s3", region_name=AWS_REGION)

def _key_for(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower() or ".bin"
    return f"uploads/{uuid.uuid4().hex}{ext}"

def upload_fileobj(fileobj, filename: str):
    """
    Uploads to S3. Returns (key, url). If S3_PUBLIC=False, url is a presigned URL.
    """
    key = _key_for(filename)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    extra = {"ContentType": ctype}
    if S3_PUBLIC:
        extra["ACL"] = "public-read"
    _s3.upload_fileobj(fileobj, S3_BUCKET, key, ExtraArgs=extra)
    return key, url_for_key(key)

def url_for_key(key: str, expires=3600) -> str:
    if S3_PUBLIC:
        return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
    return _s3.generate_presigned_url(
        "get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=expires
    )
