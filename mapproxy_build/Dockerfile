FROM python:3.12-alpine AS base-libs

ARG NGINX_VERSION=1.25.3
ENV MAPPROXY_ALPINE=true

RUN apk -U upgrade --update \
    && apk add \
      g++ \
      gdal \
      gdal-dev \
      libxslt-dev \
      libxml2 \
      proj \
      proj-dev \
      proj-util \
      geos \
      geos-dev \
      libffi-dev \
    && rm -rf /var/cache/apk/*

RUN mkdir /mapproxy && addgroup -S mapproxy && \
    adduser -D -s /bin/sh -S -h /mapproxy/ -G mapproxy mapproxy

USER mapproxy:mapproxy

WORKDIR /mapproxy

RUN python -m venv venv && source venv/bin/activate && \
  pip --disable-pip-version-check install MapProxy requests redis boto3 azure-storage-blob && \
  pip cache purge

COPY app.py .
COPY entrypoint.sh .
COPY config ./config_template
#COPY config/uwsgi.conf ./config_template/uwsgi.conf
#COPY config/logging.ini ./config_template/logging.ini
#COPY config/mapproxy-example.yaml ./config_template/mapproxy.yaml

USER root
RUN chmod 0755 app.py entrypoint.sh
#RUN chown mapproxy:mapproxy app.py config/uwsgi.conf config/mapproxy-example.yaml

##### nginx to server requests to uwsgi ######

USER root:root

RUN apk --no-cache add ca-certificates uwsgi uwsgi-python3 supervisor pcre-dev && \
  rm -rf /var/cache/apk/*

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]

CMD ["echo", "no CMD given"]
