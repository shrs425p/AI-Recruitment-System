import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config
from ai_mode import get_providers

PLACEHOLDERS = {'sk-ant-...','sk-...','AIza...','gsk_...','nvapi-...','ghp_...','sk-or-...'}

def key_valid(p):
    if p['name'] == 'ollama_cloud':
        return True
    key = p.get('key', '').strip()
    return bool(key) and key not in PLACEHOLDERS

providers = get_providers()
print('=== Provider Status ===')
for p in providers:
    valid = key_valid(p)
    if p['enabled'] and valid:
        status = 'ENABLED + VALID KEY'
    elif p['enabled']:
        status = 'ENABLED but PLACEHOLDER/EMPTY KEY'
    else:
        status = 'disabled'
    key_preview = p.get('key','')[:20] + '...' if len(p.get('key','')) > 20 else p.get('key','')
    print(f"  {p['name']:<20} {status}  key={key_preview}")

print()
print('APP_MODE:', config.APP_MODE)
active = [p for p in providers if p['enabled'] and key_valid(p)]
print('Active providers for routing:', [p['name'] for p in active])
print()
if active:
    print('READY — cloud routing is functional.')
else:
    print('PROBLEM — no valid active providers found.')
    print('Check: NVIDIA_ENABLED =', config.NVIDIA_ENABLED)
    print('Check: NVIDIA_KEY    =', repr(config.NVIDIA_KEY[:30]))
