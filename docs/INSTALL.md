# Install Guide

This guide assumes:

- you already have Docker working on the Plex host
- your Plex media is mounted somewhere on the host
- you are comfortable copying files and editing a text file

If that is true, the setup is straightforward.

One important note before you start:

- every path, username, and email shown in this repo is an example
- you are expected to replace them with the values that make sense on your own server

## 1. Put the repo on the Plex host

Clone or copy the repository to the server. In the example below, we use:

```bash
/opt/subgen
```

If you choose a different location, that is fine. Just be consistent when you install the systemd service later.

## 2. Check your media paths

Open `docker-compose.yml` and look at the `volumes:` section.

The example uses:

```yaml
- /srv/media/PlexFilmsHD:/media/PlexFilmsHD
- /srv/media/PlexFilms:/media/PlexFilms
- /srv/media/PlexTVHD:/media/PlexTVHD
- /srv/media/PlexTV:/media/PlexTV
```

The left side is the real path on your server.
The right side is the path Subgen sees inside the container.

If your server stores media somewhere else, change the left side only.

## 3. Check your user and group IDs

In the same compose file, check:

```yaml
- PUID=1000
- PGID=1001
```

These tell the container which Linux user and group to act as when it reads and writes files.

If subtitles are not being written, wrong IDs are one of the first things to check.

To find the right values on your host:

```bash
id
```

## 4. Create the model folder

The compose file expects this folder to exist:

```bash
/opt/subgen/models
```

Create it if needed:

```bash
mkdir -p /opt/subgen/models
```

Subgen will download Whisper models into that folder.

## 5. Start Subgen

From the repo folder:

```bash
docker compose up -d
```

Then check the container:

```bash
docker ps
docker logs --tail 100 subgen
curl http://127.0.0.1:9000/status
```

If everything is healthy, `/status` should return a small JSON response with the Subgen version.

## 6. Set up the monitor

The monitor script does two jobs:

- it keeps a readable summary of failures
- it deletes files that repeatedly break processing, so the queue does not get stuck

Copy the example file:

```bash
cp monitor.env.example monitor.env
```

You can leave it mostly unchanged if you do not want email alerts yet.

## 7. Install the monitor as a service

Copy the systemd unit:

```bash
sudo cp systemd/subgen-monitor.service /etc/systemd/system/subgen-monitor.service
```

Then reload systemd and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now subgen-monitor.service
```

Check it:

```bash
systemctl status subgen-monitor.service
```

## 8. Know where to look later

These are the most useful files after install:

- `docker logs subgen`
  Live Subgen activity
- `monitor/subgen_failed_files.txt`
  Human-readable summary
- `monitor/subgen_failed_events.log`
  Detailed event history

## 9. Optional: email alerts

Email is only used for one thing here:

- a file looks like it should be English based on audio metadata, but Whisper detects another language

That usually means one of two things:

- the file metadata is wrong
- the content includes a lot of non-English dialogue

To enable email, fill in the SMTP settings in `monitor.env`.

If you leave them blank, the system still works. It just records those events without sending mail.

## 10. How to tell it is really working

Healthy logs usually look like one of these:

- "Skipping ... Subtitles already exist in English."
- "WORKER START ..."
- "Detected language: English"
- "WORKER FINISH ..."

That means the queue is alive and Subgen is making decisions.

## 11. If CPU use feels too high

The first settings to change are:

- `WHISPER_THREADS`
- `WHISPER_MODEL`
- `cpus`

Lowering them makes the server calmer, but slower.

The included defaults are a compromise rather than a benchmark winner.
