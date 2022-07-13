# Fog Computing: Prototyping Assignment - E-Bike Station

## Usage
Move cloud and edge folders to the respective machines and change ips and ports in .env files correspondingly.
### On the edge
```
python bike_station/application.py

```
starts to generate fake sensor data (spot is occupied or not, battery level) and electricity info (self-consumption, feed-in, revenue etc.) and queues them on database for possible failure scenarios.
```
python client.py

```
tries to connect and send summarized info to cloud.

```
python server.py

```
handles incoming connections from cloud.

### On the cloud
```
python application.py

```
generates fake reservations from users for random duration and write these entries to database.
```
python client/client.py

```
tries to connect and send reservation data along with current electricity market price to edge.

```
python server/server.py

```
handles incoming connections from edge.



## Dockerfile
Both edge and cloud servers can be run with docker, too.<br />
To build image(e.g for server at edge):
```
docker build -t edge_server .

```
To run container with persisted volume:
```
docker run --rm  -v <abolute_path_to_sqlite_db>:/edge/sqlite.db -p 5555:5555 edge_server

```


## Cleaning up
Command below cleans up sqlite database(already processed entries) on edge with 1 hour interval.
Add this command to crontab file (crontab -e)
```

0 * * * * <path to python executable which contains required libs> <path_to>/edge/clean_db.py

```
