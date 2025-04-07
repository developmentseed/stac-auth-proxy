ARG STAC_AUTH_PROXY_VERSION
FROM ghcr.io/developmentseed/stac-auth-proxy:${STAC_AUTH_PROXY_VERSION}

ADD . /opt/stac-auth-proxy-integration

RUN pip install /opt/stac-auth-proxy-integration
