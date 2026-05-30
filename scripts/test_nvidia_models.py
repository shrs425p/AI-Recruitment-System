import sys, json, urllib.request, urllib.error
sys.path.insert(0, 'config')
import config

KEY  = config.NVIDIA_KEY
BASE = 'https://integrate.api.nvidia.com/v1/chat/completions'

candidates = [
    'meta/llama-3.1-8b-instruct',
    'meta/llama-3.2-3b-instruct',
    'meta/llama-3.3-70b-instruct',
    'nvidia/llama-3.1-nemotron-nano-8b-instruct',
    'nvidia/llama-3.3-nemotron-super-49b-v1',
    'mistralai/mistral-7b-instruct-v0.3',
    'google/gemma-7b',
    'microsoft/phi-3-mini-4k-instruct',
]

print("Testing NVIDIA NIM models with your API key...\n")
for model in candidates:
    payload = {'model': model, 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 5}
    req = urllib.request.Request(
        BASE,
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            reply = data['choices'][0]['message']['content'][:30]
            print("WORKS  " + model + "  ->  " + reply)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:100]
        print("ERROR  " + model + "  HTTP " + str(e.code) + ": " + body[:70])
    except Exception as ex:
        print("ERROR  " + model + "  " + str(ex)[:80])
