# Configuration Guide

This is not a full Subgen reference. It is the shortlist of settings that actually matter in this setup.

## `cpus: 8.0`

This is the broad "do not get greedy" limit.

It tells Docker not to let the container use much more than eight CPU cores in total. That gives Subgen room to work without letting it sprawl all over the machine.

If the server feels too busy, lower it.
If the server has plenty of headroom, you can raise it, but do it gradually.

## `PUID` and `PGID`

These tell the container which Linux user and group it should act as.

If these are wrong, the usual symptoms are boring but annoying:

- Subgen can read files but not write subtitles
- subtitle files are created with awkward ownership
- permissions look wrong even though the container itself is running fine

In most setups these should match the account that already owns the media folders.

## `TRANSCRIBE_OR_TRANSLATE=translate`

This is the setting that changes the whole personality of the setup.

In simple terms:

- `transcribe` means "write subtitles in the language being spoken"
- `translate` means "write subtitles in English"

This repo uses `translate` on purpose. If you change that, you are changing the point of the setup.

## `SUBTITLE_LANGUAGE_NAME=en`

This affects how subtitle files are named.

It makes the output clearly show up as English rather than some vague custom label.

## `SHOULD_WHISPER_DETECT_AUDIO_LANGUAGE=True`

This lets Whisper work out the spoken language when needed.

That matters because translation only works properly if the system has a decent guess at what it is hearing.

## `WHISPER_MODEL=medium`

This is one of the main performance levers.

The rough trade-off is:

- smaller model = lighter and faster, but usually less accurate
- larger model = heavier and slower, but usually better

`medium` is the default here because it is a decent middle ground for a home Plex server. It is good enough to be useful without feeling needlessly heavy.

If you want it gentler on the CPU, try `small`.
If you want to push accuracy harder and have CPU to spare, try `large-v3-turbo`.

## `WHISPER_THREADS=8`

This controls how hard Whisper is allowed to lean on the CPU.

More threads usually means faster work, but also more pressure on the server. If Plex feels sluggish while Subgen is running, this is one of the first settings worth trimming.

## `CONCURRENT_TRANSCRIPTIONS=1`

This means one active job at a time, and that is deliberate.

Running several transcription jobs at once sounds efficient, but on a Plex box it often just makes everything feel busier without much satisfaction in return.

## `COMPUTE_TYPE=int8`

You do not need the low-level explanation here. The short version is:

- it is a lighter CPU-friendly inference mode
- it helps keep resource use sensible
- it is a good fit for this kind of setup

## `TRANSCRIBE_FOLDERS`

This is the list of folders Subgen watches and scans.

The format uses `|` between entries:

```text
/media/PlexFilmsHD|/media/PlexFilms|/media/PlexTVHD|/media/PlexTV
```

Only list folders you genuinely want it touching.

## `MONITOR=True`

This tells Subgen to keep watching those folders after the first scan.

Without it, you are closer to a one-off pass. With it, new files can still be picked up later.

## `PROCESS_ADDED_MEDIA=True`

This says new media should be processed.

## `PROCESS_MEDIA_ON_PLAY=False`

This says do not wait until somebody presses play before doing the work.

That is usually the better choice if you want subtitles ready in advance instead of discovered at the last possible moment.

## `SKIP_IF_TARGET_SUBTITLES_EXIST=True`

This is the main anti-duplication setting.

It effectively says:

"If English subtitles already exist, do not do the job again."

That saves time and stops the library filling up with duplicate subtitle files.

## `SKIP_IF_EXTERNAL_SUBTITLES_EXIST=True`

This is the second line of defence against duplication.

If the file already has external subtitles, Subgen will usually leave it alone.

## `CLEAR_VRAM_ON_COMPLETE=True`

This comes from the original Subgen style of config.

On a CPU-based setup it is mostly harmless. There is no real need to overthink it here.

## `MODEL_CLEANUP_DELAY=30`

This tells the script to wait a little before unloading the model after the queue goes quiet.

That helps avoid a silly pattern where the model is constantly unloaded and reloaded if a few files arrive close together.

## `SKIP_VIDEO_EXTENSIONS=.avi`

This setup skips `.avi` files.

That was left in because older containers and oddball encodes are often more trouble than they are worth. If you have AVI files you genuinely care about, you can remove it, but I would do that deliberately rather than casually.

## `NOTIFY_ON_ENGLISH_AUDIO_MISMATCH=True`

This belongs to the custom Python override, not plain stock Subgen.

It means:

- if the file metadata suggests there is English audio
- but Whisper hears another language
- record that fact and optionally send an email

It is mainly there for awkward edge cases, not for the happy path.

## Monitor settings

These live in `monitor.env`, not in the main Docker compose file.

## `AUTO_DELETE_FAILED_FILES=true`

This is the setting that deserves the most respect.

It means the monitor will delete files that repeatedly trip the known failure patterns in the Subgen logs.

Why somebody might want it:

- one bad file can jam the queue for ages
- this gives the setup a way to recover by itself

Why somebody might hesitate:

- deleted really means deleted
- a false positive would still hurt

If you want to be cautious, start with it set to `false`, watch the summary file for a while, and only turn it on once you are happy with how it behaves.

## SMTP settings

These are only needed if you want email alerts:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_USE_TLS`

If they are blank, the monitor still records the events. It just does not send any mail.

## `./subgen_override.py:/subgen/subgen.py`

This line is what turns the setup from "stock Subgen with env vars" into "stock container plus custom runtime behaviour".

If you remove it, you are no longer running this repo's behaviour. You are back to the stock Subgen script plus whatever environment variables remain.

That is fine if it is a deliberate choice. It is not the sort of thing you want to remove by accident.
