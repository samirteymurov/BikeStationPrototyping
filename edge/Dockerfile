FROM python:3.9
COPY . edge
WORKDIR edge
RUN pip3 install -r requirements.txt
ENV PYTHONPATH ".."
CMD ["python", "server.py"]
