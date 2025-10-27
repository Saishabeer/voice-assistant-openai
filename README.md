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

## ✨ Key Features

*   **🤖 Conversational AI Persona**: Features a pre-defined AI salesperson persona ("Rishi") capable of understanding needs, recommending services, and guiding users.
*   **⚡ Real-time, Two-Way Audio**: Utilizes **OpenAI's Realtime API** for low-latency transcription and simultaneous audio response generation.
*   **🔌 WebSocket Streaming**: Employs **Django Channels** for a persistent, efficient connection between the browser and the server.
*   **🛠️ Advanced Tool Integration**: Includes sophisticated logic for conversation management, such as detecting user intent to end the session.

## 🚀 How It Works

The process is a simple, elegant loop:

**Browser (Client)** `<- WebSocket ->` **Django (Server)** `<-- Realtime Session -->` **OpenAI API**

1.  **Session Start**: The browser connects to the Django server via a WebSocket.
2.  **Realtime Session**: Django initiates a `Realtime Session` with the OpenAI API, configured with the "Rishi" persona and tool directives.
3.  **Audio Streaming**: The browser captures user audio and streams it to the Django server.
4.  **AI Processing**: Django forwards the audio to the OpenAI session, which handles transcription, AI reasoning, and generating a spoken response.
5.  **Response Streaming**: OpenAI streams the AI's audio response back to Django, which immediately forwards it to the browser for playback.

## 📂 Project Structure

The repository is organized as follows:

```
live-assist/
├── .env                # Environment variables (API keys, secrets)
├── live_assist/        # Django project configuration
│   ├── asgi.py         # ASGI entry-point for Channels
│   ├── settings.py     # Project settings
│   └── urls.py         # Root URL configuration
├── manage.py           # Django's command-line utility
├── requirements.txt    # Python package dependencies
├── static/             # Frontend assets (CSS, JS)
├── templates/          # HTML templates
└── voice/              # Django app for voice handling
    ├── consumers.py    # WebSocket consumer for audio stream
    ├── constants.py    # AI prompts, models, and API endpoints
    ├── routing.py      # WebSocket URL routing
    └── views.py        # Renders the main HTML page
```

## 🛠️ Setup and Installation

1.  **Clone the repository:**

    ```sh
    git clone <repository-url>
    cd live-assist
    ```

2.  **Create and activate a virtual environment:**

    ```sh
    # Create a virtual environment
    python -m venv venv
    
    # Activate it (Windows)
    venv\Scripts\activate
    
    # Activate it (macOS / Linux)
    source venv/bin/activate
    ```

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
    # This command uses Daphne, the ASGI server required by Django Channels
    daphne -p 8000 live_assist.asgi:application
    ```

7.  **Access the application:**

    Open your web browser and go to `http://127.0.0.1:8000/`. Click "Start" and grant microphone access to begin transcription.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any bugs, feature requests, or improvements.

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them (`git commit -m 'Add some feature'`).
4.  Push to the branch (`git push origin feature/your-feature-name`).
5.  Open a Pull Request.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details..
