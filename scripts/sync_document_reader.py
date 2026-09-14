"""Bundle the canonical document rules for the standalone AgentCore runtime."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
(root / 'runtime/app/receiptreader/document_reader.py').write_bytes((root / 'basketbrief/documents.py').read_bytes())
