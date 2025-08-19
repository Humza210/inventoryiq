# storage_s3.py
import os, logging
import boto3
from botocore.config import Config

log = logging.getLogger(__name__)

S3_BUCKET  = os.getenv("S3_BUCKET", "inventoryiq-uploads")
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-2"

def _clean_env(name: str):
    v = os.getenv(name)
    if not v:
        return None
    # remove spaces, quotes, and CR/LF (Windows copy/paste bug)
    return v.strip().strip('"').strip("'").replace("\r", "").replace("\n", "")

AK = _clean_env("AWS_ACCESS_KEY_ID")
SK = _clean_env("AWS_SECRET_ACCESS_KEY")
ST = _clean_env("AWS_SESSION_TOKEN")  # may be None

_cfg = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})

# Prefer sanitized explicit env creds if present; otherwise use shared creds profile (which worked in aws_diag.py)
if AK and SK:
    _session = boto3.Session(
        aws_access_key_id=AK,
        aws_secret_access_key=SK,
        aws_session_token=ST,
        region_name=AWS_REGION,
    )
    _source = "explicit_env"
else:
    _session = boto3.Session(region_name=AWS_REGION)
    _source = "shared_creds"

s3  = _session.client("s3", region_name=AWS_REGION, config=_cfg)
sts = _session.client("sts", region_name=AWS_REGION, config=_cfg)

def assert_identity():
    ident = sts.get_caller_identity()
    c = _session.get_credentials().get_frozen_credentials()
    log.info(
        "AWS OK: acct=%s arn=%s region=%s key=...%s token=%s source=%s",
        ident.get("Account"),
        ident.get("Arn"),
        AWS_REGION,
        c.access_key[-4:],
        "yes" if c.token else "no",
        _source,
    )

def upload_fileobj(fileobj, key: str, extra: dict | None = None):
    key = (key or "").strip().lstrip("/")
    extra = extra or {}
    extra.setdefault("ContentType", "application/octet-stream")
    s3.upload_fileobj(fileobj, S3_BUCKET, key, ExtraArgs=extra)
    return key  # store key; presign when rendering

def presigned_url(key: str, expires=3600) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
