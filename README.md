# Subgen English Translation Setup for Plex

This repository packages a working Subgen setup for a Plex server that does one specific job:

- create English subtitles for media in Plex libraries
- translate non-English speech into English subtitles
- keep scanning new media automatically
- watch for bad files and remove the ones that repeatedly break Subgen
- flag cases where the audio metadata says "English" but Whisper thinks the spoken language is something else

This is not a generic Docker starter. It is a practical, opinionated setup that was built for a real Plex host and then cleaned up so somebody else can follow it without needing to reverse-engineer the moving parts.

Everything in this repository that looks like a path, username, or email address should be treated as an example placeholder unless the docs explicitly tell you otherwise.

## What is in here

- `docker-compose.yml`
  The Docker service definition for Subgen.
- `subgen_override.py`
  A custom Python override that Subgen runs instead of the stock `subgen.py`.
- `monitor_subgen_failures.py`
  A helper script that follows Subgen logs and reacts to failures.
- `monitor.env.example`
  Optional settings for the monitor, including email details.
- `systemd/subgen-monitor.service`
  A systemd unit file so the monitor stays running after reboot.
- `docs/INSTALL.md`
  A step-by-step install guide.
- `docs/CONFIGURATION.md`
  A plain-English explanation of the settings.

## Important note about the custom script

This setup uses the standard `mccloud/subgen:latest` image, but it does **not** use the stock script inside that image unchanged.

The line below mounts `subgen_override.py` over the container's own `subgen.py`:

```yaml
- ./subgen_override.py:/subgen/subgen.py
```

That means this setup is better described as:

- stock Subgen container
- custom Python runtime script
- custom failure monitor

That matters because the translation and alerting behaviour here is not just a few environment variables. Some of it lives in the Python override.

## What this setup is meant to do

The intended behaviour is:

1. If a file already has English subtitles, leave it alone.
2. If a file does not have English subtitles, try to produce them.
3. If the spoken language is not English, translate the speech into English subtitles.
4. If Subgen crashes on a specific file over and over, remove that bad file rather than letting the queue stall forever.
5. If the file metadata claims there is an English audio track but Whisper detects another language instead, log it and optionally send an email.

## What this setup is not trying to do

- It is not trying to preserve every bad file forever.
- It is not trying to make Intel Quick Sync run Whisper. Plex can use the Intel iGPU for video transcoding, but this Subgen setup runs Whisper on CPU.
- It is not trying to be "fully automatic" at the cost of hiding important decisions. A few settings are deliberately left visible and easy to edit.

## Resource profile

The included compose file is tuned to be fairly conservative on a home Plex box:

- `cpus: 8.0`
- `WHISPER_MODEL=medium`
- `WHISPER_THREADS=8`
- `CONCURRENT_TRANSCRIPTIONS=1`
- `COMPUTE_TYPE=int8`

That keeps it useful without letting it crowd out Plex too aggressively.

## Quick start

If you just want the short version:

1. Put this repo on the Plex host, for example at `/opt/subgen`.
2. Edit `docker-compose.yml` so the media paths and user IDs match your server.
3. Create the model folder if it does not already exist.
4. Start Subgen with `docker compose up -d`.
5. Copy `monitor.env.example` to `monitor.env` if you want email alerts.
6. Install the systemd monitor service.

The full version is in [docs/INSTALL.md](./docs/INSTALL.md).

## Why the docs are written this way

This repo is aimed at people who can follow instructions, not necessarily people who want to spend an evening reading Subgen source code.

So the docs try to answer the practical questions first:

- What does this setting actually do?
- What should I leave alone?
- What am I expected to change?
- What happens if I make it more aggressive?
- How do I know it is working?

## Sanity checks after install

After setup, the most useful checks are:

```bash
docker ps
curl http://127.0.0.1:9000/status
docker logs --tail 100 subgen
systemctl status subgen-monitor.service
```

You should see:

- the `subgen` container running
- a JSON response from `/status`
- log lines showing either skipped files or active work
- the monitor service in `active (running)` state

## If you want to change the behaviour

Start with [docs/CONFIGURATION.md](./docs/CONFIGURATION.md).

That file explains:

- which settings are safe to edit
- which settings affect CPU usage
- which settings control translation
- which settings control file deletion and email alerts

## Final thought

There are easier ways to publish this kind of setup, but they usually end up unreadable after a month.

The goal here is to leave behind something that still makes sense when somebody opens it six months later and asks, "Why is this here, and what happens if I change it?"
