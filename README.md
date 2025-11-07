# Live AI Voice Assistant

<div align="center">

# 🎙️ Conversational AI Sales Agent ⚡

**A real-time, browser-based conversational AI agent featuring a sales persona, powered by Django and OpenAI's next-generation Realtime API.**

</div>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white">
  <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-ES6-F7DF1E?logo=javascript&logoColor=black">
  <img alt="OpenAI" src="https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
</p>
<!-- You can add a GIF or screenshot of the application in action here! -->
<!-- ![App Screenshot](path/to/screenshot.png) -->

---

## Key Features

*   **Conversational AI Persona**: "Rishi" — understands needs, recommends services, and guides users.
*   **Real-time, Two-Way Audio (WebRTC)**: Uses OpenAI's Realtime API over WebRTC; no Django Channels/WebSockets required.
*   **AI Speaks First & English-Only**: Assistant proactively greets and always responds in English.
*   **Auth-Gated APIs + Guest UX**: Session/save/history are protected; guests see a login/signup notice.
*   **Clean persistence**: `save_conversation()` uses `SaveConversationSerializer.create()` to upsert safely.
*   **Optional analysis**: Celery task summarizes and rates satisfaction post-conversation.
*   **Organized static**: CSS in `voice/static/voice/css/`, JS in `voice/static/voice/js/`.

## How It Works

High-level flows:

**Browser (Client)** `=> WebRTC (audio + data)` **OpenAI Realtime API**

**Browser (Client)** `=> HTTP` **Django** (`/session/`, `/save-conversation/`, history APIs)

1.  **Session Start**: The browser requests `/session/` from Django to obtain an ephemeral key and instructions (persona, English-only, tools).
2.  **WebRTC Connect**: The browser establishes a direct Realtime session with OpenAI using SDP offer/answer and the ephemeral key.
3.  **AI Initiates**: On data channel open, the assistant greets first.
4.  **Live Conversation**: User audio and AI responses stream via WebRTC; transcripts render live.
5.  **Finalize & Save**: The client persists conversation snapshots; `serializer.save()` upserts; optional Celery analysis runs.

## Project Structure

The repository is organized as follows:

```
live-assist/
├── .env                       # Environment variables (API keys, secrets)
├── live_assist/               # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
├── manage.py
├── requirements.txt
├── templates/                 # HTML templates (project-level)
│   ├── voice/index.html
│   └── registration/{login.html, signup.html}
└── voice/                     # Voice app
    ├── models.py
    ├── views.py               # /session/, /save-conversation/, history APIs (auth-gated)
    ├── serializers.py         # SaveConversationSerializer.create() upsert
    ├── services/
    │   ├── analysis.py        # Post-conversation analysis (OpenAI Responses API)
    │   └── convo.py
    ├── tasks.py               # Celery task for analysis
    ├── celery_app.py          # Celery app config (optional)
    ├── constants.py           # Persona + tool directives (English-only)
    └── static/voice/
        ├── css/realtime.css
        └── js/{app.js, history.js}
```
## Setup and Installation

1.  **Clone the repository:**

    ```sh
    git clone <repository-url>
    cd live-assist
    ```

2.  **Create and activate a virtual environment:**

    - Create a virtual environment:
      ```sh
      python -m venv venv

3.  **Install the dependencies:**

    ```sh
    pip install -r requirements.txt -q
    ```

4.  **Configure environment variables:**

    Create a `.env` file in the project root and add your API keys. **Do not commit this file.**

    ```ini
    OPENAI_API_KEY=sk-...your_key_here...
    DJANGO_SECRET_KEY=your-django-secret-key
    ```

5.  **Run database migrations:**

    ```sh
    python manage.py migrate
    ```

6.  **Run the development server:**

    ```sh
    python manage.py runserver
    ```

7.  **Access the application:**

    Open your web browser and go to `http://127.0.0.1:8000/`. Click "Start" and grant microphone access to begin transcription.

---

## Data Persistence Notes

Stopping a realtime conversation now triggers a two-step save on the backend:

1. The browser first pushes the latest transcript snapshot (`finalize=false`).
2. If the session was not already finalized, the client sends a second request with `finalize=true`, `confirmed=true`, and `close=true`.

This ensures the Celery task (or synchronous fallback) persists the summary, satisfaction rating, feedback, and raw JSON payloads in `voice_conversation`.

Optional Celery (analysis):

```sh
# Worker (analysis)
celery -A voice.celery_app worker --loglevel=info

# Beat (optional scheduled jobs)
celery -A voice.celery_app beat --loglevel=info
```

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them (`git commit -m 'Add some feature'`).
4.  Push to the branch (`git push origin feature/your-feature-name`).
5.  Open a Pull Request.

---

## 🧪 Tests

- Tests run with Celery eager mode by default when you export the eager env vars as shown above.
- No Redis is required to run tests.

---

## 🛠️ Troubleshooting (Windows)

- The Python package "docker" does not install the Docker CLI. Install Docker Desktop to use the docker command, or use Memurai for Redis without Docker.
- Prefer PowerShell Start-Service Memurai over legacy net start.
- If you see PostgreSQL connection errors, ensure a local Postgres is running and the credentials in .env match.

---

## 📬 Configuration Notes

- Sensitive env vars are read from .env by live_assist/settings.py.
- For periodic tasks and Celery config, see settings.py (CELERY_* settings).
- Email delivery requires valid SMTP credentials and may need App Passwords for Gmail.

---

## 📄 License

MIT — see LICENSE for details.