"""Define custom exceptions."""

from fastapi.responses import HTMLResponse


class LastFMConfigError(Exception):
    """Critical error in Last.fm configuration that requires user attention."""


async def lastfm_config_exception_handler(exc: Exception) -> HTMLResponse:
    """Define custom exception handler."""
    return HTMLResponse(
        content=f"""
        <html>
            <head>
                <title>Last.fm Configuration Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; }}
                    .error-container {{
                        background-color: #ffdddd;
                        border-left: 6px solid #f44336;
                        padding: 15px;
                        margin-bottom: 15px;
                    }}
                    h1 {{ color: #d32f2f; }}
                </style>
            </head>
            <body>
                <div class="error-container">
                    <h1>Last.fm Configuration Error</h1>
                    <p>{exc!s}</p>
                    <p>Please fix this issue and restart the application.</p>
                </div>
            </body>
        </html>
        """,
        status_code=500,
    )
