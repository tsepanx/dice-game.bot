# docker build -t cubesbot:latest .
FROM python:alpine
WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY ./tglib ./tglib
COPY constants.py functions.py game.py db.py main.py ./
COPY . .

ENTRYPOINT ["python3"]
CMD ["main.py"]
