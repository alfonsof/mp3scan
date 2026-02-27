# mp3scan.py
#  This utility extracts information from an MP3 file

import sys
import os
import argparse
import io
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.mp3 import BitrateMode
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from mutagen.id3 import ID3NoHeaderError
from PIL import Image


def format_duration(seconds):
    """
    Converts duration from seconds to HH:MM:SS format.
    """
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    remaining_seconds = int(seconds)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


def detect_mp3_codification_manually(file_path, max_frames=50):
    """
    Detects MP3 bitrate encoding (CBR, VBR, ABR) by manually parsing
    a sample of audio frames from the file. This is a fallback for when
    mutagen's detection is inconclusive.
    """
    BITRATE_TABLE = {
        (1, 3): [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
        (2, 3): [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    }
    SAMPLE_RATE_TABLE = {
        0: [44100, 22050],
        1: [48000, 24000],
        2: [32000, 16000],
    }

    def parse_header(header):
        """
        Parses the MP3 frame header to extract bitrate and frame size.
        Returns (bitrate, frame_size) if the header is valid, else None.
        """
        if len(header) < 4 or header[0] != 0xFF or (header[1] & 0xE0) != 0xE0:
            return None
        version_id = (header[1] >> 3) & 0x03
        layer = (header[1] >> 1) & 0x03
        bitrate_index = (header[2] >> 4) & 0x0F
        sample_rate_index = (header[2] >> 2) & 0x03
        padding = (header[2] >> 1) & 0x01

        if version_id == 1 or layer != 1 or bitrate_index in [0, 15] or sample_rate_index == 3:
            return None

        version = 2 if version_id == 2 else 1
        bitrate = BITRATE_TABLE.get((version, 3), [None]*15)[bitrate_index]
        sample_rate = SAMPLE_RATE_TABLE.get(sample_rate_index, [None, None])[version - 1]
        frame_size = int((144000 * bitrate) // sample_rate + padding)
        return bitrate, frame_size

    with open(file_path, 'rb') as f:
        # Skip ID3 header if it exists
        if f.read(3) == b'ID3':
            f.seek(3, 1)
            size_bytes = f.read(4)
            tag_size = sum((b & 0x7F) << (7 * (3 - i)) for i, b in enumerate(size_bytes))
            f.seek(tag_size, 1)

        bitrates = []
        while len(bitrates) < max_frames:
            pos = f.tell()
            header = f.read(4)
            result = parse_header(header)
            if result:
                bitrate, frame_size = result
                bitrates.append(bitrate)
                f.seek(frame_size - 4, 1)
            else:
                f.seek(pos + 1)

        if not bitrates:
            return "No valid frames were found"
        if all(b == bitrates[0] for b in bitrates):
            return "CBR (Constant Bitrate)"
        elif len(set(bitrates)) <= 3:
            return "ABR (Average Bitrate)"
        else:
            return "VBR (Variable Bitrate)"


def detect_mp3_codification(file_path, info, max_frames=50):
    """
    Detect MP3 codification.
    First try with mutagen
    bitrate_mode:
    UNKNOWN = <BitrateMode.UNKNOWN: 0>
    Probably a CBR file, but not sure
    CBR = <BitrateMode.CBR: 1>
    Constant Bitrate
    VBR = <BitrateMode.VBR: 2>
    Variable Bitrate
    ABR = <BitrateMode.ABR: 3>
    Average Bitrate (a variant of VBR)
    """
    if hasattr(info, 'bitrate_mode'):
        mode = info.bitrate_mode
        if mode == BitrateMode.CBR:
            return "CBR (Constant Bitrate)"
        elif mode == BitrateMode.VBR:
            return "VBR (Variable Bitrate)"
        elif mode == BitrateMode.ABR:
            return "ABR (Average Bitrate)"
        else:
            # If Mutagen does not detect mode, then it uses manual analysis
            return detect_mp3_codification_manually(file_path, max_frames)


def get_embedded_image_dimensions(tags):
    """
    Extracts the dimensions of the first embedded image (APIC frame) from tags.

    Returns:
        tuple[int, int] | tuple[None, None]: A tuple of (width, height) or
                                             (None, None) if no image is found.
    """
    if not tags:
        return None, None

    for tag in tags.values():
        if isinstance(tag, APIC):  # Embedded image
            image_bytes = tag.data
            image = Image.open(io.BytesIO(image_bytes))
            return image.width, image.height
    return None, None


def get_size_file(file_path):
    """
    Gets the size of a file after verifying it's a media file supported by Mutagen.

    Returns:
        int | None: The file size in bytes, or None if the file is not a
                    supported media type.
    """
    audio = File(file_path)
    if not audio:
        return None
    return os.path.getsize(file_path)


def mode_to_text(mode_value):
    """
    Converts the MP3 channel mode integer to a human-readable string.
    """
    modes = {
        0: "Stereo",
        1: "Joint Stereo",
        2: "Dual Channel",
        3: "Mono"
    }
    return modes.get(mode_value, "Unknown")


def unpack(value):
    """
    Unpacks a list if it contains elements, returning the first element.
    Otherwise returns the value as is.
    """
    if isinstance(value, list) and len(value) > 0:
        return value[0]
    return value


def extract_lyrics(tags):
    """
    Extracts lyrics from ID3 tags.

    It searches for lyrics in USLT (Unsynchronized Lyrics) frames first,
    then falls back to custom TXXX frames with a 'lyrics' description.

    Returns:
        tuple[str, str, str]: A tuple containing the lyric frame type (e.g., "USLT"),
                              the lyrics text, and the length as a formatted string.
                              Returns ("", "N/A", "N/A") if no lyrics are found.
    """
    if not tags:
        return "", "N/A", "N/A"

    # Search for any USLT frame (Unsynchronized Lyrics)
    uslt_frames = tags.getall("USLT")

    if uslt_frames: # We take the first USLT frame return uslt_frames[0].text
        # We took the first USLT frame found
        lyrics_type = "USLT"
        lyrics_text = uslt_frames[0].text
        return lyrics_type, lyrics_text, f"{len(lyrics_text)} characters"

    #  Search for custom TXXX lyrics (lyrics-XXX)
    txxx_frames = tags.getall("TXXX")
    for frame in txxx_frames:
        # frame.desc = field name (e.g., "lyrics-eng")
        if "lyrics" in frame.desc.lower():
            lyrics_type = "TXXX"
            # frame.text is a list, we take the first element
            lyrics_text = frame.text[0]
            return lyrics_type, lyrics_text, f"{len(frame.text[0])} characters"

    # If there are no letters in any format
    return "", "N/A", "N/A"


def get_mp3_tech_info(file_path, audio):
    """
    Extracts technical audio information from a Mutagen audio object.

    Returns:
        dict: A dictionary containing formatted technical details like bitrate,
              sample rate, duration, etc.
    """
    # --- Technical Information (audio.info) ---
    info = audio.info

    # Layer 1, 2, or 3
    layer_map = { 1: "Layer I", 2: "Layer II", 3: "Layer III" }
    layer = f"{info.layer} ({layer_map.get(info.layer, 'Unknown')})"

    # MPEG version (1, 2, 2.5)
    version_layer_map = { 1: "MPEG-1", 2: "MPEG-2", 2.5: "MPEG-2.5" }
    version = f"{info.version} ({version_layer_map.get(info.version, 'Unknown')})"

    file_type = f"MP3 (MPEG audio layer {info.layer})"

    # Encoder
    encoder_info = getattr(info, 'encoder_info', None)
    if not encoder_info and 'TSSE' in audio:
        # TSSE is a TextFrame, Mutagen handles it as a list of strings
        encoder_info = str(audio['TSSE'])
    final_encoder_code = encoder_info if encoder_info else 'N/A (Not found in info or TSSE frame)'
    encoder = final_encoder_code

    # File size
    file_size = get_size_file(file_path)
    size = f"{file_size/1024:.2f} KB ({file_size} bytes)"

    # Bitrate
    bitrate_kbps = info.bitrate // 1000 if info.bitrate else "N/A"
    bitrate = f"{bitrate_kbps} kbps"
    
    # Sample Rate
    sample_rate = f"{info.sample_rate} Hz"
    
    # Duration
    duration_seconds = info.length
    duration_formatted = format_duration(duration_seconds)
    duration = f"{duration_formatted} ({duration_seconds:.2f} seconds)"
    
    # Bit Rate Type (CBR, VBR, ABR)
    bitrate_mode = detect_mp3_codification(file_path, info)
    
    # Channel Mode: STEREO, JOINTSTEREO, DUALCHANNEL, or MONO (0-3)
    channel_mode_raw = getattr(info, 'mode', 'N/A')
    # Robustly handle the '0' return value if the mode info is missing or corrupted
    if channel_mode_raw == 'N/A':
        channel_mode = 'N/A (Mode info unavailable)'
    else:
        channel_mode = mode_to_text(channel_mode_raw)

    # Channels
    channels = getattr(info, 'channels', 'N/A')

    return {
        "Layer": layer,
        "Version": version,
        "File Type": file_type,
        "Encoder (Code)": encoder,
        "Size": size,
        "Bitrate": bitrate,
        "Sample Rate": sample_rate,
        "Duration": duration,
        "Bitrate Type": bitrate_mode,
        "Channel Mode": channel_mode,
        "Channels": channels
    }


def get_mp3_metadata(file_path, audio):
    """
    Extracts metadata (ID3 tags) from a Mutagen audio object.

    Returns:
        dict: A dictionary containing common ID3 tags like title, artist,
              album, etc.
    """
    # Try to load with EasyID3 for common tags
    try:
        tags = EasyID3(file_path)
    except ID3NoHeaderError:
        # If no EasyID3 header, load basic ID3
        tags = audio 

    return {
            "Title": unpack(tags.get("title", ["N/A"])),
            "Artist": unpack(tags.get("artist", ["N/A"])),
            "Album": unpack(tags.get("album", ["N/A"])),
            "Album artist": unpack(tags.get("albumartist", ["N/A"])),
            "Year": unpack(tags.get("date", ["N/A"])),   # Use 'date' which is more standard in EasyID3
            "Genre": unpack(tags.get("genre", ["N/A"])),
            "Track Number": unpack(tags.get("tracknumber", ["N/A"])),
            "Disc Number": unpack(tags.get("discnumber", ["N/A"])),
            "Composer": unpack(tags.get("composer", ["N/A"])),
            "Comment": unpack(tags.get("comment", ["N/A"])),
            "Encoded by": unpack(tags.get("encodedby", ["N/A"])),
    }


def get_info_lyrics(tags):
    """
    Extracts and formats lyrics information into a dictionary for display.

    Returns:
        dict: A dictionary containing the lyric type, length, and the
              lyrics themselves.
    """
    lyrics_type, lyrics, lyrics_length = extract_lyrics(tags)

    return {
            f" Lyrics - [{lyrics_type}] Length": lyrics_length,
            f" Lyrics - [{lyrics_type}]": lyrics
    }

    
def get_info_cover(audio):
    """
    Retrieves information from the image embedded in an MP3.

    This function inspects the APIC (Attached Picture) frame to get details
    like MIME type, size, and dimensions.

    Returns:
        dict: A dictionary of image properties or a message if not found.
    """
    # --- Album Art (APIC) ---
    # Album art is accessed directly from the MP3/ID3 object
    if 'APIC:' in audio:
        apic = audio['APIC:']
        mime_type = apic.mime
        description = apic.desc
        size = f"{len(apic.data) / 1024:.2f} KB"
        width, height = get_embedded_image_dimensions(audio.tags)
        return {
            "  MIME Type": mime_type,
            "  Description": description,
            "  Size": size,
            "  Width": width,
            "  Height": height
        }
    else:
        return {"Embedded Image": "Not found"}


def print_content(variable):
    """
    Prints the key-value pairs of a dictionary with aligned formatting.
    """
    for  key, value in variable.items():
        print(f"{key.ljust(15)}: {value}")


def print_raw_audio_data(audio):
    """
    Prints raw Mutagen audio object attributes for debugging purposes.
    """
    print("\nRAW DATA - AUDIO")
    print("-" * 16)
    for k, v in vars(audio).items():
        print(k, ":", v)

    print("\nRAW DATA - TECH INFO")
    print("-" * 20)
    #print(vars(audio.info))
    for k, v in vars(audio.info).items():
        print(k, ":", v)

    print("\nRAW DATA - TAGS")
    print("-" * 15)
    for k, v in audio.tags.items():
        print(k, ":", v)

    print("-" * 30)
    return


def get_mp3_info(file_path, debug=False):
    """
    Extracts and displays technical audio information and ID3 metadata
    from an MP3 file using the Mutagen library.
    """
    print(f"\n{'='*50}")
    print(f"   📋 ANALYZING FILE: {os.path.basename(file_path)}")
    print(f"{'='*50}\n")

    try:
        audio = MP3(file_path)  # Read MP3 data using mutagen library

        if debug:
            print_raw_audio_data(audio)
        
        print("\n🔊 TECHNICAL AUDIO INFORMATION")
        print("-" * 30)
        
        tech_info = get_mp3_tech_info(file_path, audio)
        print_content(tech_info)

        print("\n📝 METADATA (ID3 TAGS)")
        print("-" * 22)

        tags = get_mp3_metadata(file_path, audio)
        print_content(tags)

        print(f"\nLyrics:")
        lyrics = get_info_lyrics(audio.tags)
        print_content(lyrics)
    
        print(f"\nAlbum Art (APIC) - Embedded Image:")
        cover = get_info_cover(audio)
        print_content(cover)

    except Exception as e:
        print(f"\n❌ An error occurred while processing the file: {e}")

    print(f"\n{'='*50}\n")


if __name__ == "__main__":
    # Command-line argument parser setup
    parser = argparse.ArgumentParser(
        description="Extracts and displays technical information and ID3 metadata from an MP3 file."
    )
    parser.add_argument(
        "mp3_file", 
        type=str, 
        help="The full path to the MP3 file to analyze."
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Print raw audio data for debugging."
    )
    
    args = parser.parse_args()

    mp3_file = args.mp3_file

    if not os.path.exists(mp3_file):
        print(f"❌ Error: The file '{mp3_file}' was not found.")
        sys.exit(1)

    get_mp3_info(mp3_file, debug=args.debug)
