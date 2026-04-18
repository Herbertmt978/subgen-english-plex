# Configuration Guide

This file explains the important settings in plain English.

Not every option in Subgen is listed here. Only the ones that matter for this setup.

## Docker-level settings

### `cpus: 8.0`

This is a Docker limit.

It tells Docker not to let this container use more than roughly eight CPU cores in total.

Why it is here:

- Subgen can be quite heavy while transcribing.
- Plex still needs room to breathe.

If your server feels too busy:

- lower this to `6.0` or `4.0`

If the server is powerful and mostly idle:

- you can raise it, but do it gradually

## File access settings

### `PUID` and `PGID`

These tell the container which Linux user and group it should behave as.

Why they matter:

- if they are wrong, Subgen may read files but fail to write subtitles
- or it may write files with awkward permissions

For most people, these should match the account that already owns the media folders.

## Core behaviour

### `TRANSCRIBE_OR_TRANSLATE=translate`

This is the setting that makes the setup produce English subtitles from non-English speech.

In simple terms:

- `transcribe` means "write subtitles in the same language that is spoken"
- `translate` means "write subtitles in English"

This repo uses `translate` on purpose.

### `SUBTITLE_LANGUAGE_NAME=en`

This tells Subgen how to name the subtitle files it creates.

So instead of a vague custom label, the output is clearly marked as English.

### `SHOULD_WHISPER_DETECT_AUDIO_LANGUAGE=True`

This tells the script to let Whisper detect the spoken language when needed.

That matters because translation only works properly if the system has a decent idea what language it is hearing.

## Performance settings

### `WHISPER_MODEL=medium`

This chooses the Whisper model size.

Roughly speaking:

- smaller model = lighter, faster, less accurate
- larger model = heavier, slower, usually more accurate

Why `medium` is used here:

- it is a sensible middle ground for a home Plex host
- it avoids the heavier footprint of `large-v3-turbo`

If you want to be gentler on the CPU:

- try `small`

If you care more about accuracy and have CPU to spare:

- try `large-v3-turbo`

### `WHISPER_THREADS=8`

This controls how many CPU threads Whisper is allowed to use.

More threads usually means faster work, but also more pressure on the server.

For non-technical users, the easiest rule is:

- if Plex feels sluggish while Subgen runs, lower this
- if the server is calm and you want faster subtitle generation, raise it slowly

### `CONCURRENT_TRANSCRIPTIONS=1`

This means only one item is actively processed at a time.

That is deliberate.

Running several jobs at once sounds attractive, but in practice it often makes the server feel worse without giving a neat, predictable speed-up.

### `COMPUTE_TYPE=int8`

This is a lighter inference mode for the CPU.

You do not need to understand the low-level details. The short version is:

- it helps reduce resource use
- it is a sensible choice for CPU-based Whisper on a home server

## Library scanning

### `TRANSCRIBE_FOLDERS`

This is the list of media folders Subgen should watch and scan.

The format uses `|` between folders:

```text
/media/PlexFilmsHD|/media/PlexFilms|/media/PlexTVHD|/media/PlexTV
```

Only include the folders you actually want processed.

### `MONITOR=True`

This tells Subgen to keep watching those folders for new files.

So once the initial scan is done, it can still pick up new media later.

### `PROCESS_ADDED_MEDIA=True`

This tells it to process newly added files.

### `PROCESS_MEDIA_ON_PLAY=False`

This tells it not to wait until someone presses play before doing work.

That is usually the better choice if you want subtitles ready in advance.

## Subtitle safety checks

### `SKIP_IF_TARGET_SUBTITLES_EXIST=True`

This says:

"If English subtitles already exist, do not do the job again."

That is one of the most important safety settings in the file.

It prevents wasted work and duplicate subtitles.

### `SKIP_IF_EXTERNAL_SUBTITLES_EXIST=True`

This is another protection against duplication.

If the file already has external subtitles present, Subgen will usually leave it alone.

## Cleanup and stability

### `CLEAR_VRAM_ON_COMPLETE=True`

This comes from the original Subgen configuration style.

On a CPU-based setup it is mostly harmless, and leaving it enabled is fine.

### `MODEL_CLEANUP_DELAY=30`

This tells the script to wait a little before unloading the model after the queue goes idle.

That helps avoid constant unloading and reloading if several files arrive close together.

### `SKIP_VIDEO_EXTENSIONS=.avi`

This setup skips `.avi` files entirely.

That was left in place because older container formats and odd encodes are more likely to be trouble than help.

If your library has important AVI files you really want handled, you can remove this, but do it with your eyes open.

## Alerting and custom behaviour

### `NOTIFY_ON_ENGLISH_AUDIO_MISMATCH=True`

This is part of the custom Python override.

It means:

- if the file metadata suggests English audio
- but Whisper detects another language
- write that down and optionally send an email

This is useful for catching awkward edge cases.

For example:

- a Korean or French film tagged strangely
- mixed-language content
- bad metadata inside the file

## Monitor settings

These live in `monitor.env`, not the Docker compose file.

### `AUTO_DELETE_FAILED_FILES=true`

This is a strong setting.

It means the monitor will delete files that repeatedly trip the known failure patterns in Subgen logs.

Why somebody might want this:

- one bad file can jam the queue for ages
- the monitor acts as a self-healing safety valve

Why somebody might not want this:

- deleted really means deleted
- a false positive would still remove the file

If you prefer a safer mode at first:

- set this to `false`
- watch the summary file for a while
- turn it on later when you are comfortable

### SMTP settings

These are only needed if you want email alerts:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_USE_TLS`

If these are blank, the monitor still logs the events. It just does not send any mail.

## The one setting most people should not touch

### `./subgen_override.py:/subgen/subgen.py`

This line is what makes the setup run the custom script.

If you remove it, you are no longer using this customised behaviour. You are back to stock Subgen behaviour plus whatever environment variables remain.

That is fine if it is a deliberate choice. It is not fine if it happens by accident.
