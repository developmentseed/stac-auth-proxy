# Installation and Running

## Docker

The simplest way to run the project is via our [published Docker image](https://github.com/developmentseed/stac-auth-proxy/pkgs/container/stac-auth-proxy):

```sh
docker run \
  -it --rm \
  -p 8000:8000 \
  -e UPSTREAM_URL=https://my-stac-api \
  -e OIDC_DISCOVERY_URL=https://my-auth-server/.well-known/openid-configuration \
  ghcr.io/developmentseed/stac-auth-proxy:latest
```

## Python

### Installation

The application can be installed as a standard [Python module](https://pypi.org/project/stac-auth-proxy):

```sh
pip install stac-auth-proxy
```

### Running

The installed Python module can be invoked directly:

```sh
python -m stac_auth_proxy
```

Alternatively, the application's factory can be passed to Uvicorn:

```sh
uvicorn --factory stac_auth_proxy:create_app
```

## Docker Compose

For development and experimentation, the codebase (ie within the repository, not within the Docker or Python distributions) ships with a `docker-compose.yaml` file, allowing the proxy to be run locally alongside various supporting services: the database, the STAC API, and a Mock OIDC provider.

### pgSTAC Backend

Run the application stack with a pgSTAC backend using [stac-fastapi-pgstac](https://github.com/stac-utils/stac-fastapi-pgstac):

```sh
docker compose up
```

### OpenSearch Backend

Run the application stack with an OpenSearch backend using [stac-fastapi-elasticsearch-opensearch](https://github.com/stac-utils/stac-fastapi-elasticsearch-opensearch):

```sh
docker compose --profile os up
```
