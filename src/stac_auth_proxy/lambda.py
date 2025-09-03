"""Handler for AWS Lambda."""

from stac_auth_proxy import create_app

try:
    from mangum import Mangum
except ImportError:
    raise ImportError(
        "mangum is required to use the Lambda handler. Install stac-auth-proxy[lambda]."
    )


handler = Mangum(
    create_app(),
    # NOTE: lifespan="off" skips conformance check and upstream health checks on startup
    lifespan="off",
)
