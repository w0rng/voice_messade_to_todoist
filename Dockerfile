FROM python:3.11-slim as builder

WORKDIR app
RUN pip install -U pip setuptools wheel pdm
COPY ./pyproject.toml ./pdm.lock ./
RUN mkdir __pypackages__ &&\
    pdm install --prod --no-lock --no-editable

FROM jrottenberg/ffmpeg:4.4-alpine AS FFmpeg
FROM python:3.11-alpine
RUN apk update && apk add --no-cache ffmpeg
WORKDIR /app

COPY --from=builder /app/__pypackages__/3.11 /pkgs
COPY src .
ENV PYTHONPATH "${PYTHONPATH}:/pkgs/lib"
ENV PATH "${PATH}:/pkgs/bin"
CMD ["python", "main.py"]
