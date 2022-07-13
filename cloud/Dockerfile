FROM python:3.9
COPY . cloud
WORKDIR cloud
RUN pip3 install -r requirements.txt
ENV PYTHONPATH ".."
CMD ["python", "server/server.py"]
