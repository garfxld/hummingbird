#!/usr/bin/env python3
"""
Download a YouTube playlist via yt-dlp and fix metadata tags.

Fixes:
  - album_artist: extracted as the primary (first) artist from the track's artist tag
  - track number: set from the playlist order
  - album: set from --album if provided
  - disc: set to 1

The download itself embeds the artist/album from the source, but for YouTube
auto-generated uploads these are frequently incomplete (e.g. no album_artist,
no track number). The script corrects those tags in a single re-mux per file.

Usage:
  python3 playlist_download.py <playlist_url> [--album "Album Name"] [--artist "Primary Artist"]
  python3 playlist_download.py <playlist_url> -o /path/to/output/dir
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


def extract_primary_artist(artist_tag: str) -> str:
    """Extract the primary artist from a comma-separated artist string."""
    parts = re.split(r"[,，]", artist_tag)
    return parts[0].strip()


def read_tags(filepath: str) -> dict:
    """Read format-level tags from an audio file via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", filepath,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {}
    data = json.loads(result.stdout)
    return data.get("format", {}).get("tags", {})


def write_tags(filepath: str, tags: dict) -> bool:
    """Write all tags to a file in one pass, preserving the audio stream."""
    outpath = os.path.join(os.path.dirname(filepath), f".tmp_meta_{os.path.basename(filepath)}")
    cmd = ["ffmpeg", "-y", "-i", filepath, "-c", "copy", "-map_metadata", "0"]
    for key, value in tags.items():
        cmd.extend(["-metadata", f"{key}={value}"])
    cmd.append(outpath)

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"  ERROR: ffmpeg failed for {os.path.basename(filepath)}", file=sys.stderr)
        if os.path.exists(outpath):
            os.remove(outpath)
        return False

    shutil.move(outpath, filepath)
    return True


def download_playlist(url: str, output_dir: str, template: str) -> list[str]:
    """Download a playlist, returning output file paths in playlist order."""
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=mp3]/bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "--add-metadata",
        "-o", template,
        "--no-overwrites",
        url,
    ]
    print(f"Downloading playlist to {output_dir} ...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("yt-dlp failed", file=sys.stderr)
        sys.exit(1)

    # The template puts a zero-padded playlist index at the front of each
    # filename, so numeric sort == playlist order.
    def index_sort_key(name: str) -> int:
        match = re.match(r"^(\d+)", name)
        return int(match.group(1)) if match else 10**9

    files = sorted(
        (f for f in os.listdir(output_dir) if f.endswith(".mp3")),
        key=index_sort_key,
    )
    return [os.path.join(output_dir, f) for f in files]


def fix_metadata(
    files: list[str],
    album: str | None = None,
    primary_artist: str | None = None,
):
    """Fix album_artist, track number, album, and disc on each file."""
    for i, filepath in enumerate(files, start=1):
        basename = os.path.basename(filepath)
        print(f"  Fixing [{i:2d}] {basename}")

        tags = read_tags(filepath)
        changes: dict[str, str] = {}

        artist_tag = tags.get("artist", "").strip()
        album_artist = primary_artist or (extract_primary_artist(artist_tag) if artist_tag else None)
        if not album_artist:
            print("    WARNING: no artist tag found, leaving album_artist unset")
        elif tags.get("album_artist") != album_artist:
            changes["album_artist"] = album_artist

        if tags.get("track") != str(i):
            changes["track"] = str(i)

        if album and tags.get("album") != album:
            changes["album"] = album

        if tags.get("disc") != "1":
            changes["disc"] = "1"

        if changes:
            set_str = ", ".join(f"{k}={v}" for k, v in changes.items())
            if write_tags(filepath, changes):
                print(f"    set: {set_str}")
        else:
            print("    no changes needed")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download a YouTube playlist via yt-dlp and fix metadata tags. "
            "Sets album_artist (primary artist), track numbers from playlist "
            "order, disc=1, and optionally an album name."
        ),
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="YouTube playlist URL")
    parser.add_argument("-o", "--output", default=None,
                        help="Output directory (default: ~/Music/<album or 'downloads'>)")
    parser.add_argument("--album", default=None,
                        help="Album name to set on all tracks")
    parser.add_argument("--artist", default=None,
                        help="Primary artist (album_artist). Auto-detected from the "
                             "artist tag if omitted.")
    args = parser.parse_args()

    if not shutil.which("yt-dlp"):
        print("yt-dlp not found in PATH. Install it first: "
              "e.g. `pip install yt-dlp` or `brew install yt-dlp`", file=sys.stderr)
        sys.exit(1)

    album_name = args.album or "downloads"
    output_dir = args.output or os.path.expanduser(f"~/Music/{album_name}")
    os.makedirs(output_dir, exist_ok=True)

    template = os.path.join(output_dir, "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s")

    files = download_playlist(args.url, output_dir, template)
    if not files:
        print("No files were downloaded", file=sys.stderr)
        sys.exit(1)

    print(f"\nDownloaded {len(files)} tracks. Fixing metadata ...\n")
    fix_metadata(files, album=args.album, primary_artist=args.artist)

    print(f"\nDone. {len(files)} tracks saved to {output_dir}")


if __name__ == "__main__":
    main()