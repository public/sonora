FROM python:3.8.1-buster AS base

WORKDIR /usr/src/app

RUN apt update && \
    apt install -y build-essential libev-dev

COPY . .

RUN pip install -e .[tests]

RUN python -m grpc.tools.protoc \
        --proto_path="$(pwd)/" \
        --python_out=. \
        --grpc_python_out=. \
        "$(pwd)"/test_server/*.proto

RUN pip install daphne

FROM base AS wsgi

CMD python test_server/wsgi.py

FROM base AS asgi

CMD daphne -b 0.0.0.0 -p 8080 test_server.asgi:application