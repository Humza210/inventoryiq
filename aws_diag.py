# aws_diag.py
import os, io, uuid, sys, reprlib
import boto3
from botocore.config import Config

def show_env(name):
    v = os.getenv(name)
    # repr shows hidden \r, spaces, quotes if any
    print(f"{name} = {repr(v)} len={0 if v is None else len(v)}")

print("ENV (repr):")
for k in ["AWS_PROFILE","AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY","AWS_SESSION_TOKEN","AWS_REGION","AWS_DEFAULT_REGION","S3_BUCKET"]:
    show_env(k)

region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
bucket = os.getenv("S3_BUCKET","inventoryiq-uploads")

cfg = Config(signature_version="s3v4", s3={"addressing_style":"virtual"})
# IMPORTANT: build session from env only, no profile fallback
session = boto3.Session(
    aws_access_key_id=(os.getenv("AWS_ACCESS_KEY_ID") or "").strip() or None,
    aws_secret_access_key=(os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip() or None,
    aws_session_token=(os.getenv("AWS_SESSION_TOKEN") or "").strip() or None,
    region_name=region
)

creds = session.get_credentials()
if not creds:
    print("No credentials resolved by boto3 session — check your .env / shell", file=sys.stderr)
    sys.exit(1)
fc = creds.get_frozen_credentials()
print(f"Using access key last4: {fc.access_key[-4:]}; session_token? {'yes' if fc.token else 'no'}")

s3 = session.client("s3", region_name=region, config=cfg)
sts = session.client("sts", region_name=region, config=cfg)

print("\nCaller identity:")
print(sts.get_caller_identity())

print("\nHeadBucket (to discover real region if mismatch):")
try:
    s3.head_bucket(Bucket=bucket)
    print("HeadBucket OK")
except Exception as e:
    print("HeadBucket error:", e)

key = f"diagnostics/{uuid.uuid4().hex}.txt"
print(f"\nUpload test to s3://{bucket}/{key} (region={region}) ...")
try:
    s3.upload_fileobj(io.BytesIO(b"diag"), bucket, key, ExtraArgs={"ContentType":"text/plain"})
    print(f"OK -> https://{bucket}.s3.{region}.amazonaws.com/{key}")
except Exception as e:
    print("Upload error:", e)
