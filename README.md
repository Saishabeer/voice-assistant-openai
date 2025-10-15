# Live AI Voice Assistant

<div align="center">

# 🎙️ Live AI Voice Assistant ⚡

**A real-time, browser-based voice transcription tool powered by Django and OpenAI's Whisper API.**

</div>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white">
  <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-ES6-F7DF1E?logo=javascript&logoColor=black">
  <img alt="OpenAI" src="https://img.shields.io/badge/OpenAI-Whisper-412991?logo=openai&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
</p>

<!-- You can add a GIF or screenshot of the application in action here! -->
<!-- ![App Screenshot](path/to/screenshot.png) -->

---

## ✨ Key Features

*   **Live Transcription**: Captures microphone audio directly in the browser and displays the transcript in real-time.
*   **Low-Latency Streaming**: Uses **WebSockets** for an efficient, near-instant connection between your browser and the server.
*   **High-Accuracy ASR**: Leverages **OpenAI's Whisper API** for state-of-the-art speech-to-text conversion.
*   **Simple & Modern Stack**: Built with **Python/Django** on the backend and vanilla **HTML/CSS/JS** on the frontend.

## 🚀 How It Works

The process is a simple, elegant loop:

**Browser (Client)** `->` **Django (Server)** `->` **OpenAI (API)** `->` **Django (Server)** `->` **Browser (Client)**

1.  **Capture**: The browser records 1-second audio chunks using the `MediaRecorder` API.
2.  **Stream**: Each chunk is sent to the Django server via a WebSocket.
3.  **Transcribe**: The server forwards the audio to the OpenAI Whisper API.
4.  **Return**: OpenAI sends the transcript text back to the server.
5.  **Display**: The server pushes the text back to the browser, which appends it to the page.

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
