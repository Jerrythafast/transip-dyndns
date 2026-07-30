FROM python:3-alpine

WORKDIR /service

RUN pip install cryptography requests

COPY . ./

ENTRYPOINT ["python3", "app.py"]