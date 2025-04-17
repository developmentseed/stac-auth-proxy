"""
In order to allow customization fo the Swagger UI's OAuth2 configuration, we support
overriding the default handler. This is useful for adding custom parameters such as
`usePkceWithAuthorizationCodeGrant` or `clientId`.

See:
- https://swagger.io/docs/open-source-tools/swagger-ui/usage/oauth2/
"""

from dataclasses import dataclass, field
from typing import Optional

from fastapi.openapi.docs import get_swagger_ui_html
from starlette.requests import Request
from starlette.responses import HTMLResponse


@dataclass
class SwaggerUI:
    """Swagger UI handler."""

    openapi_url: str
    title: Optional[str] = "STAC API"
    init_oauth: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    oauth2_redirect_url: str = "/docs/oauth2-redirect"

    async def route(self, req: Request) -> HTMLResponse:
        """Route handler."""
        root_path = req.scope.get("root_path", "").rstrip("/")
        openapi_url = root_path + self.openapi_url
        oauth2_redirect_url = self.oauth2_redirect_url
        if oauth2_redirect_url:
            oauth2_redirect_url = root_path + oauth2_redirect_url
        return get_swagger_ui_html(
            openapi_url=openapi_url,
            title=f"{self.title} - Swagger UI",
            oauth2_redirect_url=oauth2_redirect_url,
            init_oauth=self.init_oauth,
            swagger_ui_parameters=self.parameters,
        )
