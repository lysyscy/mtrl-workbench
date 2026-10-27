"""Capture an existing preview page and its verified instance identity, never start a server."""
from datetime import datetime, timezone
import hashlib
import json
import re
from tools.audit.workspace_paths import output
from tools.dev.frontend_preview_runtime import active_preview, assert_same_preview


def capture_preview(page, expected_owner, label):
    stamp=datetime.now(timezone.utc).strftime('%H%M%S-%f')
    name=re.sub(r'[^a-zA-Z0-9_-]+','-',label).strip('-')[:70] or 'page'
    path=output(f'{name}-{stamp}.png',kind='screenshots')
    metadata={'label':label,'url':page.url,'viewport':page.viewport_size,
        'captured_at':datetime.now(timezone.utc).isoformat(),
        'owner':{key:expected_owner.get(key) for key in ('process','schema','revision','backend_commit','product_digest','index_sha256')}}
    try:
        assert_same_preview(expected_owner,active_preview()[1])
        metadata['identity_verified']=True
    except Exception as exc:
        # A failed/offline instance is useful failure evidence, never a verified live result.
        metadata.update(identity_verified=False,identity_error=type(exc).__name__)
    page.screenshot(path=str(path),full_page=False)
    metadata['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return path
