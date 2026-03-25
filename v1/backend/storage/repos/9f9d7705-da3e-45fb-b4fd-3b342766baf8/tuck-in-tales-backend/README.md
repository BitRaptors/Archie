# Tuck-in Tales Backend

This directory contains the FastAPI backend for the Tuck-in Tales application.

## Setup

1.  **Prerequisites:** Ensure you have Python (>=3.10 recommended) and [Poetry](https://python-poetry.org/docs/#installation) installed.
2.  **Navigate:** Open your terminal and change to this directory:
    ```bash
    cd tuck-in-tales-backend
    ```
3.  **Install Dependencies:** Install the required Python packages using Poetry:
    ```bash
    poetry install
    ```
4.  **Environment Variables:** This project uses a `.env` file to manage sensitive information and configuration. Copy the example or create your own `.env` file in this directory (`tuck-in-tales-backend/.env`) with the following variables:
    ```dotenv
    # .env file
    SUPABASE_URL="your_supabase_project_url"
    SUPABASE_ANON_KEY="your_supabase_anon_key"
    SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key" # Keep secure!

    OPENAI_API_KEY="your_openai_api_key"
    # Optional: Specify models if different from defaults
    # OPENAI_CHAT_MODEL="gpt-4o"
    # OPENAI_EMBEDDING_MODEL="text-embedding-3-small"

    FIREBASE_SERVICE_ACCOUNT_KEY_PATH="./firebase-service-account.json" # Path relative to backend root

    # Other settings if needed (e.g., for LangSmith tracing)
    # LANGCHAIN_TRACING_V2="true"
    # LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
    # LANGCHAIN_API_KEY="your_langsmith_api_key"
    # LANGCHAIN_PROJECT="your_langsmith_project_name"
    ```
    *   Replace the placeholder values with your actual Supabase, OpenAI, and Firebase credentials.
    *   Ensure the `firebase-service-account.json` file exists at the specified path (or update the path).

## Running the Backend

Once the setup is complete, you can run the FastAPI development server using Uvicorn:

```bash
poetry run uvicorn src.main:app --reload
```

*   `src.main:app`: Points Uvicorn to the FastAPI application instance (`app`) located in the `src/main.py` file.
*   `--reload`: Enables auto-reloading, so the server restarts automatically when you make code changes.

The server will typically start on `http://127.0.0.1:8000`. You can access the API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.
