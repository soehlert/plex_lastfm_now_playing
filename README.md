# Plex Last.fm "Now Playing" Scrobbler
[![Docker Build and Push to GHCR](https://github.com/soehlert/plex_lastfm_now_playing/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/soehlert/plex_lastfm_now_playing/actions/workflows/docker-publish.yml)

This application listens for webhook events from your Plex Media Server and updates your Last.fm "Now Playing" status in real-time. The built in Plex scrobbler only scrobbles after the track is over, and some other attempts seem to time out halfway through a song. This should fix both of those problems.

## Configuration

The application is configured using environment variables. You will need to gather the following information:

*   **`LASTFM_API_KEY`**: Your Last.fm API Key. You can get one from [Last.fm API Accounts](https://www.last.fm/api/account/create).
*   **`LASTFM_API_SECRET`**: Your Last.fm API Shared Secret.
*   **`LASTFM_USERNAME`**: Your Last.fm username.
*   **`LASTFM_PASSWORD_HASH`**: The MD5 hash of your Last.fm password. **Do not use your plain password.** You can generate an MD5 hash using command-line tools:
    *   Linux/macOS: `echo -n "yourpassword" | md5sum` (or `md5`)
*   **`UPDATE_INTERVAL_SECONDS`**: An optional override of the default (60) second time to update Last.FM
*   **`PAUSE_TIMEOUT_SECONDS`**: An optional override of the default (10) second time before a pause is considered a stop

## Installation and Running

You can run this application using Docker (amd64 or arm64) or as a systemd service on a Linux system.

### Method 1: Using Docker Compose (Recommended)

**Prerequisites:**
*   [Docker](https://docs.docker.com/get-docker/) installed.
*   [Docker Compose](https://docs.docker.com/compose/install/) installed.

**Steps:**

1.  **Create a `docker-compose.yml` file:**
    Create a file named `docker-compose.yml` with the following content:

    ```yaml
    services:
      plex-lastfm-now-playing:
        image: ghcr.io/soehlert/plex_lastfm_now_playing:latest
        container_name: plex_lastfm_now_playing
        restart: unless-stopped
        ports:
            - "8000:8000"
        # Set up to read env vars from portainer
        environment:
            - LASTFM_API_KEY=${LAST_API_KEY}
            - LASTFM_API_SECRET=${LASTFM_API_SECRET}
            - LASTFM_USERNAME=${LASTFM_USERNAME}
            - LASTFM_PASSWORD_HASH=${LASTFM_PASSWORD_HASH}
            # Override if you want
            - UPDATE_INTERVAL_SECONDS=${UPDATE_INTERVAL_SECONDS}  # defaults to 60 seconds
            - PAUSE_TIMEOUT_SECONDS=${PAUSE_TIMEOUT_SECONDS} # how long until the pause is considered a stop - default 10s
        # Uncomment envfile stuff if you want to use that instead of the individual env vars
        #env_file:
        #    - ./.env
    ```
    Optional env_file:

    ```yaml
    LASTFM_API_KEY=your_lastfm_api_key_here
    LASTFM_API_SECRET=your_lastfm_api_secret_here
    LASTFM_USERNAME=your_lastfm_username_here
    LASTFM_PASSWORD_HASH=your_md5_password_hash_here
    # Override if you want
    UPDATE_INTERVAL_SECONDS=some_sort_of_integer_seconds
    PAUSE_TIMEOUT_SECONDS=some_sort_of_integer_seconds
    ```
2. **Start the application:**
   Open a terminal in the directory where you created the docker-compose.yml file and run:

    ```Bash
    docker-compose up -d
    ```

### Method 2: Running as a systemd service (Linux)
This method involves installing the application directly on your Linux system and running it under systemd.

Prerequisites:
* Python 3.12+
* uv - [installer](https://docs.astral.sh/uv/getting-started/installation/).
* git
* A dedicated user to run the application (recommended for security, e.g., scrobbler).

Steps:

1. **Clone the repository:**
    ```bash
    git clone https://github.com/soehlert/plex_lastfm_now_playing /usr/local/plex_lastfm_now_playing
    chown scrobbler:scrobbler /usr/local/plex_lastfm_now_playing
    cd /usr/local/plex_lastfm_now_playing
    ```
2. **Create a virtual environment**
    ```bash
    uv venv
    ```
3. **Activate the virtual environment**
    ```bash
    source .venv/bin/activate
    ```

4. **Install the application and its dependencies using uv**
    ```bash
    uv sync
    ```
5. **Configure Environment Variables for systemd:**
Create an environment file for the service. For example, at /etc/plex_lastfm_now_playing/config.env:
    ```bash
    sudo mkdir -p /etc/plex_lastfm_now_playing
    sudo nano /etc/plex_lastfm_now_playing/config.env
    ```
6. **Add your configuration from the previous envfile example to this file:**
7. **Secure the file:**
    ```bash
    sudo chown scrobbler:scrobbler /etc/plex_lastfm_now_playing/config.env
    sudo chmod 600 /etc/plex_lastfm_now_playing/config.env
    ```
8. **Create the systemd Service File:**
     Create a file named plex-lastfm-now-playing.service in /etc/systemd/system/
    ```bash
    [Unit]
    Description=Plex Last.fm Now Playing Scrobbler
    After=network.target
    
    [Service]
    User=scrobbler
    Group=scrobbler
    WorkingDirectory=/usr/local/plex_lastfm_now_playing
    EnvironmentFile=/etc/plex_lastfm_now_playing/config.env
    
    ExecStart=/usr/local/plex_lastfm_now_playing/.venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker plex_lastfm_now_playing.plex_lastfm_now_playing:app --bind 0.0.0.0:8000
    
    Restart=always
    RestartSec=3
    
    [Install]
    WantedBy=multi-user.target
    ```
9. **Pick up the new service and start it:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable plex-lastfm-now-playing.service
    sudo systemctl start plex-lastfm-now-playing.service
    ```
## Plex Configuration
Once the application is running (either via Docker or systemd), you need to configure Plex to send webhooks to it.

1. In Plex, go to Settings > Webhooks.
2. Click Add Webhook.
3. Enter the URL where your plex-lastfm-now-playing application is listening. Eg:
    ```bash
    https://10.10.10.1:8000/webhook
    ```
4. Save the webhook.

Plex will now send notifications to your application when media playback starts, stops, or pauses.

