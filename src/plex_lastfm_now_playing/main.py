"""Define fastAPI endpoints."""

import json
import logging.config
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import pydantic
from fastapi import FastAPI, Form, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from .exceptions import LastFMConfigError, lastfm_config_exception_handler
from .models import AuthResponse, PlexWebhookPayload
from .plex_lastfm_now_playing import LastFmUpdater, PlexWebhookHandler

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Global instances (managed by lifespan context)
app_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Manage application startup and shutdown logic."""
    logger.info("Application startup")
    # Create instances needed for the application lifetime
    app_state["lastfm_updater"] = LastFmUpdater()
    app_state["webhook_handler"] = PlexWebhookHandler(app_state["lastfm_updater"])
    yield
    logger.info("Application shutdown")
    handler = app_state.get("webhook_handler")
    if handler:
        # Gracefully stop any running background task on shutdown
        await PlexWebhookHandler.shutdown(reason="Application shutdown")
    logger.info("Cleanup complete.")


app = FastAPI(lifespan=lifespan, title="Plex Last.fm Now Playing Scrobbler")

app.add_exception_handler(LastFMConfigError, lastfm_config_exception_handler)


@app.post("/webhook")
async def plex_webhook_endpoint(payload: str = Form(...)) -> dict[str, str]:
    """Receives webhooks from Plex Media Server."""
    webhook_handler = app_state.get("webhook_handler")
    if not webhook_handler:
        logger.error("Webhook handler not initialized.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

    try:
        data = json.loads(payload)
        if data["event"] in ["media.play", "media.resume"]:
            logger.info("Received webhook payload: %s", data)
        parsed_payload = PlexWebhookPayload.model_validate(data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from e
    except (pydantic.ValidationError, TypeError, ValueError) as e:  # Catch specific errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload structure") from e

    try:
        await webhook_handler.process_webhook(parsed_payload)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {e!s}") from e
    return {"message": "Webhook received"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Check health."""
    return {"status": "ok"}


@app.get("/setup/lastfm", response_model=AuthResponse)
async def setup_lastfm() -> AuthResponse | dict[str, str]:
    """Start the Last.fm authentication process."""
    lastfm_updater = app_state.get("lastfm_updater")
    if not lastfm_updater:
        raise HTTPException(status_code=500, detail="Last.fm updater not initialized")

    if not lastfm_updater.setup_mode:
        raise HTTPException(status_code=400, detail="Last.fm updater is not in setup mode")

    try:
        _, auth_url = lastfm_updater.generate_auth_url(lastfm_updater.network)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {
            "auth_url": auth_url,
            "message": "Please visit this URL to authorize the application, then return to /setup/lastfm/complete",
        }


@app.get("/setup/lastfm/complete")
async def complete_lastfm_setup(username: str = Query(..., description="Your Last.fm username")) -> dict[str, str]:
    """Complete the Last.fm authentication process."""
    lastfm_updater = app_state.get("lastfm_updater")
    if not lastfm_updater:
        raise HTTPException(status_code=500, detail="Last.fm updater not initialized")

    if not lastfm_updater.setup_mode:
        raise HTTPException(status_code=400, detail="Last.fm updater is not in setup mode")

    try:
        await lastfm_updater.complete_auth(username)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return {"message": "Authentication successful!"}


@app.get("/setup", response_class=HTMLResponse)
async def setup_page() -> str:
    """Provide a simple HTML interface for the setup process."""
    lastfm_updater = app_state.get("lastfm_updater")
    if not lastfm_updater or not lastfm_updater.setup_mode:
        return """
        <html>
            <head><title>Setup Not Required</title></head>
            <body>
                <h1>Setup Not Required</h1>
                <p>The application is already configured and running normally.</p>
            </body>
        </html>
        """

    return """
    <html>
        <head><title>Last.fm Setup</title></head>
        <body>
            <h1>Last.fm Setup</h1>
            <p>This page will help you set up Last.fm authentication for this application.</p>

            <h2>Step 1: Start Authentication</h2>
            <button onclick="startAuth()">Start Last.fm Authentication</button>

            <div id="step2" style="display:none; margin-top: 20px;">
                <h2>Step 2: Complete Authentication</h2>
                <p>After authorizing on Last.fm, enter your Last.fm username:</p>
                <input type="text" id="username" placeholder="Your Last.fm username">
                <button onclick="completeAuth()">Complete Setup</button>
            </div>

            <div id="result" style="display:none; margin-top: 20px;">
                <h2>Setup Complete!</h2>
            </div>

            <script>
                async function startAuth() {
                    try {
                        const response = await fetch('/setup/lastfm');
                        const data = await response.json();

                        // Open the auth URL in a new tab
                        window.open(data.auth_url, '_blank');

                        // Show step 2
                        document.getElementById('step2').style.display = 'block';
                    } catch (error) {
                        alert('Error starting authentication: ' + error);
                    }
                }

                async function completeAuth() {
                    const username = document.getElementById('username').value;
                    if (!username) {
                        alert('Please enter your Last.fm username');
                        return;
                    }

                    try {
                        const response = await fetch(`/setup/lastfm/complete?username=${encodeURIComponent(username)}`);
                        const data = await response.json();

                        // Show the result
                        document.getElementById('result').style.display = 'block';
                    } catch (error) {
                        alert('Error completing authentication: ' + error);
                    }
                }
            </script>
        </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="::", port=8000)
