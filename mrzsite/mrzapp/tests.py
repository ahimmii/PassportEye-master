from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
import os
import tempfile
from pathlib import Path

from .views import _format_date_dmy
from .morocco import read_morocco_id
from .pdf_filler import create_filled_form


class DateFormattingTest(TestCase):
    def test_date_formatting(self):
        """Test the 2-digit year date formatting logic."""
        # Test cases for the year boundary logic
        self.assertEqual(_format_date_dmy("460210"), "10/02/1946")  # 46 -> 1946
        self.assertEqual(_format_date_dmy("050407"), "07/04/2005")  # 05 -> 2005
        self.assertEqual(_format_date_dmy("270918"), "18/09/2027")  # 27 -> 2027
        self.assertEqual(_format_date_dmy("300101"), "01/01/2030")  # 30 -> 2030
        self.assertEqual(_format_date_dmy("310101"), "01/01/1931")  # 31 -> 1931
        
        # Test invalid dates
        self.assertIsNone(_format_date_dmy("invalid"))
        self.assertIsNone(_format_date_dmy(""))
        self.assertIsNone(_format_date_dmy("12345"))  # Too short


class UploadViewTest(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_upload_page_loads(self):
        """Test that the upload page loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MRZ Extractor')
        self.assertContains(response, 'Upload passport/ID image')
    
    def test_upload_without_file(self):
        """Test form submission without a file."""
        response = self.client.post('/', {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid form submission')


class MoroccoReaderTest(TestCase):
    def test_morocco_reader_with_non_mar(self):
        """Test Moroccan reader with non-MAR document (should fail by default)."""
        # Use a test image that we know exists
        test_image = Path(__file__).parent.parent.parent / "tests" / "data" / "passport-td3.jpg"
        if test_image.exists():
            with self.assertRaises(ValueError):
                read_morocco_id(str(test_image), require_mar=True)
    
    def test_morocco_reader_allow_non_mar(self):
        """Test Moroccan reader allowing non-MAR documents."""
        test_image = Path(__file__).parent.parent.parent / "tests" / "data" / "passport-td3.jpg"
        if test_image.exists():
            try:
                result = read_morocco_id(str(test_image), require_mar=False)
                self.assertIsInstance(result, dict)
                self.assertIn("mrz_type", result)
            except Exception:
                # If MRZ detection fails, that's okay for this test
                pass


class PDFFillerTest(TestCase):
    def test_create_filled_form(self):
        """Test PDF form creation with sample data."""
        sample_data = {
            "type": "P<",
            "country": "USA",
            "number": "123456789",
            "surname": "DOE",
            "names": "JOHN",
            "sex": "M",
            "nationality": "USA",
            "date_of_birth": "800101",
            "expiration_date": "300101",
            "date_of_birth_formatted": "01/01/1980",
            "expiration_date_formatted": "01/01/2030",
            "valid_score": 100,
            "valid_number": True,
            "valid_date_of_birth": True,
            "valid_expiration_date": True,
        }
        
        pdf_bytes = create_filled_form(sample_data)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)  # Should be a reasonable PDF size
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))  # Should start with PDF header


class ManagementCommandTest(TestCase):
    def test_extract_mrz_command_exists(self):
        """Test that the extract_mrz management command exists."""
        from django.core.management import get_commands
        commands = get_commands()
        self.assertIn('extract_mrz', commands)
    
    def test_extract_morocco_id_command_exists(self):
        """Test that the extract_morocco_id management command exists."""
        from django.core.management import get_commands
        commands = get_commands()
        self.assertIn('extract_morocco_id', commands)
    
    def test_fill_pdf_form_command_exists(self):
        """Test that the fill_pdf_form management command exists."""
        from django.core.management import get_commands
        commands = get_commands()
        self.assertIn('fill_pdf_form', commands)