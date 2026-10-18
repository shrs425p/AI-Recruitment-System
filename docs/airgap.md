# Air-Gapped & Offline Architecture

The AI Recruitment System is designed to operate in completely disconnected, air-gapped environments where no inbound or outbound internet access is available.

---

## Architecture Principles

```
┌─────────────────────────────────────────────────────────────┐
│                   AIR-GAPPED ENVIRONMENT                    │
│                                                             │
│  ┌──────────────────────┐        ┌───────────────────────┐  │
│  │   HR Desktop App     │        │   Candidate Portal    │  │
│  │ 127.0.0.1:5001 (LAN) │        │  <LAN-IP>:5000 (TLS)  │  │
│  └──────────┬───────────┘        └───────────┬───────────┘  │
│             │                                │              │
│             ▼                                ▼              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Bundled Static Assets                    │  │
│  │  - Fonts: Inter & JetBrainsMono (app/static/fonts/)   │  │
│  │  - Visuals: Chart.js (app/static/js/chart.umd.min.js) │  │
│  └───────────────────────────────────────────────────────┘  │
│             │                                │              │
│             ▼                                ▼              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Offline Local Engines                    │  │
│  │  - Local LLM: Ollama (http://127.0.0.1:11434)         │  │
│  │  - Local OCR: Bundled Tesseract Engine                │  │
│  │  - Local Vision: OpenCV Haar Cascade XML              │  │
│  │  - Database: Local Encrypted SQLite File              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              X
                              | No Outbound Calls
                              ▼
                      Public Internet
```

---

## 1. Zero External CDN Dependencies

Traditional web applications rely on public content delivery networks (CDNs) for fonts, stylesheets, and charting libraries. In air-gapped secure networks, CDN requests fail, resulting in unstyled interfaces or broken charts.

ARS bundles all required assets directly inside the application repository:

### Bundled Typography
All UI font definitions in `app/templates/` use locally hosted web fonts stored in `app/static/fonts/`:
- **Inter Font Family (`.woff2`):** Primary UI sans-serif typography.
- **JetBrainsMono Font Family (`.woff2`):** Monospace font used for code snippets, JSON viewers, and terminal outputs.

### Bundled Charting Engine
Interactive charts and data visualizations on the Dashboard and Talent Intelligence pages load from `app/static/js/chart.umd.min.js`. No outbound calls to `cdn.jsdelivr.net` or `cdnjs.cloudflare.com` occur.

---

## 2. Fully Local AI and Machine Learning

In **Privacy Mode** (the default operational mode), the application guarantees that no resume text, candidate responses, or scoring prompts leave the local system.

### Local LLM via Ollama
- All resume extraction, candidate ranking rubrics, adaptive interview question generation, and report evaluations execute through a local Ollama daemon (`http://127.0.0.1:11434`).
- Recommended models: `llama3.2:3b`, `mistral:7b`, or `qwen2.5:7b`.
- The system automatically handles local model timeouts, fallback parsing, and JSON repair without requiring external network connectivity.

### Local Optical Character Recognition (OCR)
- Scanned PDF resumes, photographs, and document images are extracted using a self-contained Tesseract OCR engine located in `models/Tesseract-OCR/`.
- Does not call external vision APIs or cloud OCR services.

### Local Computer Vision & Proctoring
- Real-time face tracking during candidate interviews runs via OpenCV using bundled Haar cascade classifiers (`haarcascade_frontalface_default.xml`).
- Web camera frames are processed in-memory in a background thread and never saved to disk or transmitted over the network.

---

## 3. Network Boundary Isolation

The system enforces strict interface binding separation between administrative HR operations and external candidate access:

| Service | Bound Interface | Security Policy |
|---|---|---|
| **HR Desktop Application** | `127.0.0.1:5001` | Strictly accessible on localhost. External network devices cannot connect. |
| **Candidate Portal** | `0.0.0.0:5000` (HTTPS) | Accessible across the local subnetwork via candidate-specific tokens. All HR management routes return 404 on this port. |

---

## 4. Verification and Automated Air-Gap Tests

Air-gap integrity is enforced through continuous regression tests in [`tests/test_airgap.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_airgap.py):

1. **Asset File Verification:** Verifies that Inter font files, JetBrainsMono font files, and `chart.umd.min.js` physically exist in `app/static/`.
2. **Template Audit:** Scans every HTML file in `app/templates/` to assert that zero references to `fonts.googleapis.com`, `fonts.gstatic.com`, `cdnjs.cloudflare.com`, `cdn.jsdelivr.net`, or other third-party CDN domains exist.

To verify air-gap compliance locally:
```bash
pytest tests/test_airgap.py -v
```
