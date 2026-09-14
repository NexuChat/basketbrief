"""AgentCore adapter. Run scripts/sync_document_reader.py before deployment."""
import os
import threading
from document_reader import read_document, as_source_text

MODEL = os.environ.get('BASKETBRIEF_VISION_MODEL', 'us.amazon.nova-pro-v1:0')
_local = threading.local()

def read_receipt(image_bytes, client=None):
    if client is None:
        if getattr(_local, 'client', None) is None:
            import boto3
            from botocore.config import Config
            _local.client = boto3.Session(region_name=os.environ.get('AWS_REGION', 'us-east-1')).client(
                'bedrock-runtime', config=Config(read_timeout=45, connect_timeout=8, retries={'max_attempts':1}))
        client = _local.client
    return read_document(image_bytes, client, MODEL)
