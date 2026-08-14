# FAQ

Frequently asked questions.

---

## General

### Can I use this without an internet connection?

Yes — set **App Mode** to **Privacy** in Settings → AI Providers. In Privacy mode, all AI calls go to a local Ollama server running on your machine. You also need:
- Ollama installed and running (`ollama serve`)
- A model pulled locally (`ollama pull llama3.2:3b`)
- Vosk model present at `models/vosk-model-small-en-in-0.4/` (bundled)
- Tesseract OCR present at `models/Tesseract-OCR/` (bundled)

The candidate portal, email, and Google Calendar integration require a network connection if used.

---

### Can multiple HR users access the dashboard at the same time?

The HR dashboard is served on `127.0.0.1:5001` (localhost only). Only the machine running the app can access it through the desktop window. If you want another HR user to access it from a different machine, you would need to change `ARS_DESKTOP_PORT` and open the firewall — but this is not a supported configuration and has security implications since HTTP is not encrypted on LAN.

The **candidate portal** (port 5000) is designed for multi-device access and runs over HTTPS.

---

### Does this store candidate data in the cloud?

No. All data — resumes, NLP profiles, interview transcripts, reports — is stored locally in `%LOCALAPPDATA%\AI Recruitment System\`. The only external communication is:
- AI API calls (if cloud providers are enabled) — resume/answer text is sent to the provider
- Google Calendar API (if configured)
- SMTP server (for scheduling emails)

If you use Privacy mode with local Ollama, no candidate data leaves the machine.

---

### What happens if the AI gives a wrong score to a candidate?

The AI scoring is a starting point, not a final decision. Each score comes with a `reason` field explaining why that score was given — you can review these in the ranking output JSON. If a score looks off, check:
- Did the NLP extraction pick up all the candidate's skills correctly?
- Is the job description clear enough for the AI to understand requirements?

You can manually re-rank candidates by editing the `ranking_scores_*.json` file if needed.

---

### Can I use this for any industry, not just tech?

Yes. The NLP extractor prompt explicitly covers "IT, Software, Finance, Banking, Medical, Healthcare, Law, Legal, Marketing, Sales, HR, Education, Engineering, Architecture, Design, Research, Science, and more." The AI detects the candidate's domain automatically and the ranking is done relative to your job description — so it works for any field.

---

### What if a candidate's resume is in a language other than English?

The Vosk speech model bundled is the English-India model — voice mode will not work accurately for non-English speech. The OCR and NLP extraction depend on the AI model's language capability. Most cloud models support major languages (Hindi, Arabic, Spanish, French, etc.). Local Ollama models have more limited multilingual support depending on the model.

---

## Technical

### Why does the candidate portal use a self-signed certificate?

The candidate portal runs on a local network IP address (e.g. `192.168.1.100`), not a domain name. Certificate Authorities (like Let's Encrypt) only issue certificates for domain names, not IP addresses (with some exceptions). A self-signed certificate is the practical solution for LAN use. Candidates will see a browser warning — this is expected and safe for your own network.

---

### Can I change the Flask secret key?

Yes. Set `FLASK_SECRET_KEY` in Settings → Security. If left blank, a random key is generated on each startup, which means all existing sessions are invalidated every time the app restarts.

For persistent sessions across restarts, set a fixed key (at least 32 random characters).

---

### Why does the app use two Flask servers instead of one?

The HR dashboard must only be accessible from localhost (no external network access). The candidate portal must be accessible from other devices on the LAN. Serving both from the same server with the same host binding would either expose the HR dashboard to the network or prevent candidates from reaching the portal.

Two servers with different host bindings (`127.0.0.1` vs `0.0.0.0`) cleanly solve this — both share the same Flask app code, but access control is enforced at the network layer.

---

### Does the app support multiple simultaneous interviews?

Yes. Multiple candidates can be in active interview sessions at the same time. Each session is independent — separate question sets, separate transcripts, separate proctor instances. The Waitress server handles concurrent requests with 8 threads by default.

The webcam proctoring runs as a background thread per session. Having many simultaneous sessions with active webcam streams will use more CPU.

---

### The ranking takes a long time. How can I speed it up?

- Enable multiple AI providers — the router load-balances across them, allowing parallel scoring of different candidates from different providers simultaneously
- Increase `MAX_WORKERS` in `src/ranking_engine.py` (default is 5 parallel workers)
- Use a faster provider — Groq is particularly fast (often <1 second per call)
- Use a smaller model if response quality is acceptable

---

### Can I re-run the NLP stage for a candidate without re-uploading?

Yes. Delete the candidate's `*_nlp.json` file from `data/output/nlp/` and their `.txt` file from `data/output/txt/`. The next NLP run will re-extract from the original PDF.

Or if you just want to re-extract with a better model (after switching providers), delete only the `*_nlp.json` — the `.txt` file will be reused.

---

### What is the `_dedup_id` field in ranking output?

It is a 16-character SHA-256 hash of `name + domain + top 5 skills`. The ranking engine uses this to detect if the same resume was uploaded twice under different filenames. Duplicate entries are silently skipped — only one copy is ranked. This prevents the same candidate from appearing twice on the leaderboard.

---

### Can I use the system without the desktop window (just Flask)?

Yes. Run `python main.py` — both Flask servers start regardless of whether pywebview opens successfully. If pywebview fails (e.g. in a headless environment), the servers still run. Access the HR dashboard at `http://127.0.0.1:5001` in your browser.

---

## Interview

### What if a candidate closes their browser mid-interview?

The session data is kept in memory on the server. If the candidate re-opens their interview URL, they can resume from the last saved question. Answers are saved to the transcript as they are submitted, so nothing before the interruption is lost.

If the server restarts while a session is active, the in-memory session is lost. The candidate would need a new token.

---

### Can a candidate retake the interview?

Not automatically. Each token is for one interview run. To allow a retake, generate a new token for the candidate from the Scheduling page.

---

### What if the AI fails to evaluate an answer?

The answer is still saved to the transcript. The score and feedback fields are left empty for that question. The report will note that evaluation failed for that question. You can review the raw answer in the transcript JSON.

---

### Can I see what questions were asked after the interview?

Yes. Open the interview transcript JSON from `data/output/interviews/`. It contains the full list of questions, the candidate's answers, AI scores, and feedback for each. The PDF report also includes the full Q&A.

---

## Proctoring

### Will the proctoring work through a phone camera pointed at the screen?

It can detect faces in this scenario (the camera would see a person in front of the screen), but it is not designed to catch this case — it would look like a normal single-face detection. The proctoring is designed for a webcam facing the candidate directly.

### What if the candidate is in low light?

MediaPipe face detection is more robust than Haar cascade in low light, but both struggle with very poor lighting. If no face is detected due to poor lighting, it will be flagged as a "no face" event. The proctoring summary in the report includes the total check count, so you can assess context (e.g. if 20 out of 23 checks detected a face, the 3 no-face events are probably not concerning).

### Is the webcam footage recorded?

No. Only frame-by-frame JPEG images are processed for face detection and streamed to the HR dashboard. No video is saved to disk. Only the count of flags is stored in the transcript.
