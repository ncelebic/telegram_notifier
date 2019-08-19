FROM python:3-alpine3.10
COPY requirements.txt /
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev \
 && pip install --upgrade pip \
 && pip install -r /requirements.txt \
 && apk del .build-deps \
 && rm /requirements.txt
WORKDIR /code
ADD app.py /code/
COPY templates/* /code/templates/
ADD config.* /code/
CMD [ "python", "app.py" ]