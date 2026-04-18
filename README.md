# Subgen English Translation Setup for Plex

This repository is a cleaned-up version of a Subgen setup that was built for a real Plex server and then written up properly afterwards.

The job it is meant to do is fairly narrow:

- create English subtitles for media in Plex libraries
- translate non-English speech into English subtitles
- keep scanning new media automatically
- remove files that repeatedly break the queue
- flag cases where the file metadata says "English audio" but Whisper hears something else

It is not trying to be a universal Subgen starter kit. It is a practical setup for people who want this specific behaviour and would rather start from something lived-in than something generic.

Everything in this repo that looks like a path, username, hostname, or email address is an example placeholder. Nothing here is meant to be pasted into a live server unchanged.

One practical consequence of that:

- the Python scripts in this repo are the real logic
- the compose file, service file, and monitor example config are safe public templates
- you should expect to edit those template files before first use

## What is actually in the repo

- `docker-compose.yml`
  The container definition.
- `subgen_override.py`
  A custom Python override that replaces the stock `subgen.py` inside the container.
- `monitor_subgen_failures.py`
  A small monitor that follows the container logs and reacts to known failure cases.
- `monitor.env.example`
  Optional monitor settings, including SMTP if you want email alerts.
- `systemd/subgen-monitor.service`
  A service file so the monitor survives reboot.
- `docs/INSTALL.md`
  The install guide.
- `docs/CONFIGURATION.md`
  A plain-English explanation of the settings that matter.

## The important bit

This setup uses the standard `mccloud/subgen:latest` image, but it does not run the stock script inside that image unchanged.

This line is the key:

```yaml
- ./subgen_override.py:/subgen/subgen.py
```

So the real shape of the setup is:

- stock Subgen container
- custom runtime script
- custom monitor

That matters because some of the behaviour in this repo is not just "set these environment variables". Part of it lives in the Python override.

## How it is meant to behave

In plain terms:

1. If a file already has English subtitles, leave it alone.
2. If it does not, try to make them.
3. If the spoken language is not English, translate the speech into English subtitles.
4. If a file keeps breaking Subgen, remove it so the queue can move on.
5. If metadata claims there is English audio but Whisper detects another language, log it and optionally send an email.

## What it is not trying to do

- It is not trying to preserve every bad file forever.
- It is not trying to make Intel Quick Sync run Whisper. Plex can use the Intel iGPU for video transcoding, but Whisper itself is better suited either to CPU or to a proper NVIDIA CUDA setup.
- It is not trying to hide every decision behind "smart defaults". A few settings are left visible on purpose because they are the ones people usually need to change.

## Resource profile

The included compose file is intentionally moderate and CPU-friendly:

- `cpus: 8.0`
- `WHISPER_MODEL=medium`
- `WHISPER_THREADS=8`
- `CONCURRENT_TRANSCRIPTIONS=1`
- `COMPUTE_TYPE=int8`

That is not the fastest possible setup. It is the kind of setup you can actually live with on a Plex machine that is doing other work.

If you are running on an NVIDIA box instead, the usual changes are:

- `TRANSCRIBE_DEVICE=cuda`
- `COMPUTE_TYPE=float16`
- `gpus: all`
- a larger model such as `large-v3-turbo`

That is closer to the kind of move you would make if you want Subgen off the Plex CPU and onto a separate GPU-backed VM.

## Quick start

If you just want the short version:

1. Put the repo on the Plex host, for example at `/opt/subgen`.
2. Edit `docker-compose.yml` so the paths and user IDs match your server.
3. Create the model folder if it does not exist.
4. Start it with `docker compose up -d`.
5. Copy `monitor.env.example` to `monitor.env` if you want monitor settings of your own.
6. Install the systemd monitor service.

If you are deploying onto an NVIDIA host rather than a Plex CPU box, also switch the transcribe device and GPU-related settings first. [docs/CONFIGURATION.md](./docs/CONFIGURATION.md) now calls those out directly.

The slower, more useful version is in [docs/INSTALL.md](./docs/INSTALL.md).

If you are reading this because somebody sent you the repo link, the three files you should assume need editing are:

- `docker-compose.yml`
- `systemd/subgen-monitor.service`
- `monitor.env`

## Why the docs sound like this

Most people using something like this do not want a pile of container boilerplate. They want to know:

- what does this setting do
- what should I change
- what should I leave alone
- what will make the server noisier
- how do I know it is working

That is the angle the docs take.

## A few sanity checks

After setup, the first checks I would run are:

```bash
docker ps
curl http://127.0.0.1:9000/status
docker logs --tail 100 subgen
systemctl status subgen-monitor.service
```

What you want to see:

- the `subgen` container is running
- `/status` returns a small JSON response
- the logs show either skipped files or active work
- the monitor service is `active (running)`

## If you want to tune it

Start with [docs/CONFIGURATION.md](./docs/CONFIGURATION.md).

That file explains the settings people usually care about:

- CPU limits
- Whisper model size
- thread count
- translation mode
- duplicate-subtitle protection
- deletion behaviour in the monitor

## Final note

There are easier ways to throw a working setup onto GitHub. Most of them become annoying to trust a few months later because nobody remembers which parts were deliberate and which parts were copied from somewhere else.

The aim here was to leave behind something that still makes sense when somebody opens it later and asks: what does this actually do, and which parts are safe to change?
