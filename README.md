# Plex Last.fm "Now Playing" Scrobbler
[![Docker Build and Push to GHCR](https://github.com/soehlert/plex_lastfm_now_playing/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/soehlert/plex_lastfm_now_playing/actions/workflows/docker-publish.yml)

This application listens for webhook events from your Plex Media Server and updates your Last.fm "Now Playing" status in real-time. 
The built in Plex scrobbler only scrobbles after the track is over, and some other attempts seem to time out halfway through a song. 
This should fix both of those problems.

## Configuration

The application is configured using environment variables. You will need to gather the following information:

*   **`LASTFM_API_KEY`**: Your Last.fm API Key. You can get one from [Last.fm API Accounts](https://www.last.fm/api/account/create).
*   **`LASTFM_API_SECRET`**: Your Last.fm API Shared Secret (you'll get it with the API_KEY).

## Installation and Running

You can run this application using Docker (amd64 or arm64) or as a systemd service on a Linux system.

### Set Up
There is a guided set up upon first start. You can access it by going to http://your-instance:8000/setup. 

1. It will use your API_KEY and API_SECRET to get an auth url. 
2. You need to click that link and accept the application in last.fm. 
3. Once you've done that, go back to this site and it will ask you for your last.fm username; submit. 
4. (This part is invisible to you - it happens behind the scenes) Once you complete that, it grabs a session key and stores it
for you in a .env file in the volume specified in your docker compose file or in the path `$currentWorkingDirectory/lastfm-data/.env` NOTE: This file must be writeable on the host from Docker or your user running via systemd.

5. From now on (even after restarts), it will use your session key to authenticate you in a way that allows you to scrobble 
(the API_KEY and API_SECRET alone will not give you write permissions)

### Method 1: Using Docker Compose (Recommended)

**Prerequisites:**
*   [Docker](https://docs.docker.com/get-docker/) installed.
*   [Docker Compose](https://docs.docker.com/compose/install/) installed.

**Steps:**

1.  **Create a `docker-compose.yml` file:**
    Create a file named `docker-compose.yml` with the following content:
    Note: The application stores Last.fm credentials and session data in a persistent volume. By default, data is stored in `/opt/homelab/traefik/lastfm-data` on the host. 
    ```yaml
    services:
      plex-lastfm-now-playing:
        image: ghcr.io/soehlert/plex_lastfm_now_playing:latest
        container_name: plex_lastfm_now_playing
        restart: unless-stopped
        ports:
            - "8000:8000"
        volumes:
            - ${LASTFM_DATA_PATH:-/opt/homelab/traefik/lastfm-data}:/app/lastfm-data
        # Set up to read env vars from portainer
        environment:
            - LASTFM_API_KEY=${LASTFM_API_KEY}
            - LASTFM_API_SECRET=${LASTFM_API_SECRET}
        # Optionally use an env file instead of vars in portainer
        # env_file:
          # - .env
    ```
    Optional env_file:

    ```yaml
    LASTFM_DATA_PATH=path on the host of your .env file
    LASTFM_API_KEY=your_lastfm_api_key_here
    LASTFM_API_SECRET=your_lastfm_api_secret_here
    # Optional as we will gather this during set up if it does not exist (you likely don't want to set these on your own)
    LASTFM_USERNAME=your_lastfm_username_here
    LASTFM_SESSION_KEY=your_session_key
    # Optional to override defaults
    UPDATE_INTERVAL_SECONDS=some_sort_of_integer_seconds
    PAUSE_TIMEOUT_SECONDS=some_sort_of_integer_seconds
    APP_PORT=8000
    LOG_LEVEL="INFO"
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
* A dedicated user to run the application (recommended for security, e.g., `scrobbler`).

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
    uv pip install -e .
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
   
    ExecStart=/usr/local/plex_lastfm_now_playing/.venv/bin/fastapi run src/plex_lastfm_now_playing/main.py --proxy-headers --port 8000
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
    http://10.10.10.10:8000/webhook
    ```
4. Save the webhook.

Plex will now send notifications to your application when media playback starts, resumes, stops, or pauses (among others - you can ignore them).

