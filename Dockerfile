FROM python:3-alpine

WORKDIR /service

RUN pip install cryptography requests python-dotenv

COPY . ./

ENTRYPOINT ["python3", "dyndns.py"]
