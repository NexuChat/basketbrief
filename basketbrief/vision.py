"""Transport for the scoped document reader; interpretation lives in documents.py."""
from __future__ import annotations
import base64
import json
import os
import threading
import uuid

from .documents import SCHEMA_VERSION, amount as _decimal, as_source_text, read_document

MODEL = os.environ.get('BASKETBRIEF_VISION_MODEL', 'us.amazon.nova-pro-v1:0')
RUNTIME_ARN = os.environ.get('BASKETBRIEF_RUNTIME_ARN', '')
_local = threading.local()


def _client():
    if getattr(_local, 'client', None) is None:
        import boto3
        from botocore.config import Config
        _local.client = boto3.Session(region_name=os.environ.get('AWS_REGION', 'us-east-1')).client(
            'bedrock-runtime', config=Config(read_timeout=45, connect_timeout=10,
                                            retries={'max_attempts':1,'mode':'standard'}))
    return _local.client


def read_receipt_on_runtime(image_bytes):
    if not RUNTIME_ARN: return None
    try:
        if getattr(_local, 'runtime', None) is None:
            import boto3
            from botocore.config import Config
            _local.runtime = boto3.Session(region_name=os.environ.get('AWS_REGION', 'us-east-1')).client(
                'bedrock-agentcore', config=Config(read_timeout=90, connect_timeout=8, retries={'max_attempts':0}))
        answer = _local.runtime.invoke_agent_runtime(agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=uuid.uuid4().hex+uuid.uuid4().hex,
            payload=json.dumps({'image_b64':base64.b64encode(image_bytes).decode()}).encode())
        data = json.loads(answer['response'].read().decode())
        # An older deployment must not bypass the new document gate during rollout.
        if not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION: return None
        if data.get('status') not in ('unsupported','needs_review','extracted'): return None
        for key in ('stated_total','summed_total'):
            if data.get(key) is not None: data[key] = _decimal(data[key])
        for item in data.get('items', []):
            for key in ('qty','unit_price','line_total'):
                if item.get(key) is not None: item[key] = _decimal(item[key])
        data['where'] = 'agentcore-runtime'
        return data
    except Exception:
        return None


def read_receipt(image_bytes, client=None):
    if client is None:
        result = read_receipt_on_runtime(image_bytes)
        if result is not None: return result
        client = _client()
    return read_document(image_bytes, client, MODEL)
