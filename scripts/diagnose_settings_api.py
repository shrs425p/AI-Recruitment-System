from app import create_app
app = create_app()
with app.test_client() as c:
    r = c.post('/api/toggle-theme')
    print('/api/toggle-theme', r.status_code, r.get_data(as_text=True)[:200])
    r2 = c.post('/api/toggle-ai-mode')
    print('/api/toggle-ai-mode', r2.status_code, r2.get_data(as_text=True)[:200])
