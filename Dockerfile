FROM python:buster
WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY ./tglib ./tglib
COPY constants.py functions.py game.py main.py ./

ENTRYPOINT ["python3"]
CMD ["main.py"]
