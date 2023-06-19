FROM python:3.11-alpine
WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt
COPY ./favicons/ /app/favicons/
COPY ./main.py /app/main.py
COPY ./index.html /app/index.html
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
