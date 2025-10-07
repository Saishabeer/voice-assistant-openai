# Live AI Voice Assistant

This project is a real-time, conversational AI voice assistant built with Django and powered by the OpenAI Realtime API. It uses WebRTC for low-latency, browser-based voice communication, providing a seamless voice-to-voice interaction experience.

## Features

- **Real-time Voice Conversation**: Speak to the AI and hear its response in a continuous, low-latency stream.
- **Live Transcription**: See a live transcript of your speech as you talk.
- **Streaming AI Response**: The assistant's text and audio responses are streamed back as they are generated.
- **Customizable Persona**: Easily define the AI's personality, role, and knowledge base using an environment variable.
- **Simple Django Backend**: A lightweight backend to handle session creation and serve the frontend.

## Technologies Used

- **Backend**:
  - **Python**: The core programming language.
  - **Django**: A high-level web framework for the backend server.
  - **`httpx`**: A modern HTTP client used to communicate with the OpenAI API.
- **Frontend**:
  - **HTML, CSS, JavaScript**: For building the user interface and client-side logic.
  - **WebRTC**: Enables real-time, low-latency audio communication directly from the browser.
- **AI & Services**:
  - **OpenAI Realtime API**: Powers the live, conversational voice-to-voice experience.

## Setup and Installation

Follow these steps to get the project running on your local machine.

### 1. Clone the Repository

```sh
git clone <your-repository-url>
cd voice-assistant
```

### 2. Create a Virtual Environment

It's recommended to use a virtual environment to manage project dependencies.

```sh
# Create the virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Activate it (macOS/Linux)
source .venv/bin/activate
```

### 3. Install Dependencies

Install all the required Python packages using the `requirements.txt` file.

```sh
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root directory by copying the example below.

```sh
# .env file

DJANGO_SECRET_KEY="django-insecure-your-random-secret-key-here"
OPENAI_API_KEY="sk-your-openai-api-key-here"

# Optional: Define a custom persona for the assistant.
# If left empty, it will use the default "Rishi" persona from constants.py.
ASSISTANT_INSTRUCTIONS="You are a helpful assistant named Gemini. You are witty and concise."
```

- **`DJANGO_SECRET_KEY`**: A unique, secret key for your Django application.
- **`OPENAI_API_KEY`**: Your API key from OpenAI.
- **`ASSISTANT_INSTRUCTIONS`**: (Optional) A system prompt to define your AI's personality.

## Running the Application

1.  **Start the Django development server:**
    ```sh
    python manage.py runserver
    ```
2.  **Open your browser** and navigate to `http://127.0.0.1:8000`.
3.  Click the **Start** button and grant microphone permissions when prompted.