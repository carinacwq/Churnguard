FROM python:3.9-slim

WORKDIR /app

COPY . /app
RUN pip install -r requirements.txt

# Loading the data.xlsx file
RUN chmod +x entrypoint.sh

ENV FLASK_APP=app.py
ENTRYPOINT ["./entrypoint.sh"]
CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
