import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# We confirm that we can import the mp3scan module from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import mp3scan
from mutagen.mp3 import BitrateMode
from mutagen.id3 import APIC

class TestMp3Scan(unittest.TestCase):

    def test_format_duration(self):
        """Tests conversion from seconds to HH:MM:SS format"""
        self.assertEqual(mp3scan.format_duration(3661), "01:01:01")
        self.assertEqual(mp3scan.format_duration(65), "00:01:05")
        self.assertEqual(mp3scan.format_duration(0), "00:00:00")

    def test_mode_to_text(self):
        """Tests conversion of channel modes to text"""
        self.assertEqual(mp3scan.mode_to_text(0), "Stereo")
        self.assertEqual(mp3scan.mode_to_text(1), "Joint Stereo")
        self.assertEqual(mp3scan.mode_to_text(3), "Mono")
        self.assertEqual(mp3scan.mode_to_text(99), "Unknown")

    def test_unpack(self):
        """Tests the list unpacking function"""
        self.assertEqual(mp3scan.unpack(["item"]), "item")
        self.assertEqual(mp3scan.unpack([]), [])
        self.assertEqual(mp3scan.unpack("string"), "string")
        self.assertEqual(mp3scan.unpack(None), None)

    def test_detect_mp3_codification_cbr(self):
        """Tests CBR detection using a mocked info object"""
        mock_info = MagicMock()
        mock_info.bitrate_mode = BitrateMode.CBR
        result = mp3scan.detect_mp3_codification("dummy_path", mock_info)
        self.assertEqual(result, "CBR (Constant Bitrate)")

    def test_detect_mp3_codification_vbr(self):
        """Tests VBR detection using a mocked info object"""
        mock_info = MagicMock()
        mock_info.bitrate_mode = BitrateMode.VBR
        result = mp3scan.detect_mp3_codification("dummy_path", mock_info)
        self.assertEqual(result, "VBR (Variable Bitrate)")

    def test_extract_lyrics_uslt(self):
        """Tests lyrics extraction from a USLT frame"""
        mock_tags = MagicMock()
        mock_uslt = MagicMock()
        mock_uslt.text = "La la la"
        # Simulate getall behavior to return a list with our mock
        mock_tags.getall.return_value = [mock_uslt]
        
        lyrics_type, text, length = mp3scan.extract_lyrics(mock_tags)
        self.assertEqual(lyrics_type, "USLT")
        self.assertEqual(text, "La la la")
        self.assertIn("8 characters", length)

    def test_extract_lyrics_none(self):
        """Tests when there are no lyrics"""
        mock_tags = MagicMock()
        mock_tags.getall.return_value = []
        
        lyrics_type, text, length = mp3scan.extract_lyrics(mock_tags)
        self.assertEqual(lyrics_type, "")
        self.assertEqual(text, "N/A")
        self.assertEqual(length, "N/A")

    @patch('mp3scan.Image.open')
    def test_get_embedded_image_dimensions(self, mock_image_open):
        """Tests getting image dimensions by mocking PIL"""
        # Configure the image mock that PIL would return
        mock_image = MagicMock()
        mock_image.width = 500
        mock_image.height = 500
        mock_image_open.return_value = mock_image

        # Create a simulated APIC tag
        # Note: mp3scan checks isinstance(tag, APIC), so we use spec=APIC
        mock_apic = MagicMock(spec=APIC)
        mock_apic.data = b'fake_image_bytes'
        
        # Simulated tags dictionary
        tags = {'APIC:': mock_apic}
        
        # Execute the function
        width, height = mp3scan.get_embedded_image_dimensions(tags)
        
        self.assertEqual(width, 500)
        self.assertEqual(height, 500)

if __name__ == '__main__':
    unittest.main()
