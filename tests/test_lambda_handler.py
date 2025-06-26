import json
import sys
from unittest.mock import patch, MagicMock

sys.modules.setdefault('boto3', MagicMock())

from asn_validator.lambda_handler import lambda_handler


def test_lambda_handler_triggers_validate(tmp_path):
    # create fake files to download
    label_content = b'L'
    edi_content = b'E'

    def fake_download(bucket, key, filename):
        data = label_content if key.endswith('.pdf') else edi_content
        with open(filename, 'wb') as f:
            f.write(data)

    event = {
        'Records': [
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.pdf'}}},
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.edi'}}},
        ]
    }

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_handler.validate') as mock_validate:
        s3 = MagicMock()
        s3.download_file.side_effect = fake_download
        mock_client.return_value = s3
        mock_validate.return_value = {'ok': True}
        result = lambda_handler(event, None)

    mock_validate.assert_called_once()
    assert result == {'ok': True}


def test_lambda_handler_waits_for_companion(tmp_path):
    event = {
        'Records': [
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.pdf'}}},
        ]
    }

    class NotFound(Exception):
        def __init__(self):
            self.response = {'Error': {'Code': '404'}}

    def fake_head(Bucket, Key):
        if Key == 'a.edi':
            return {}
        raise NotFound()

    def fake_download(bucket, key, filename):
        with open(filename, 'wb') as f:
            f.write(b'x')

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_handler.validate') as mock_validate:
        s3 = MagicMock()
        s3.head_object.side_effect = fake_head
        s3.download_file.side_effect = fake_download
        mock_client.return_value = s3
        mock_validate.return_value = {'ok': True}
        result = lambda_handler(event, None)

    mock_validate.assert_called_once()
    assert result == {'ok': True}


def test_lambda_handler_missing_companion(tmp_path):
    event = {
        'Records': [
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.pdf'}}},
        ]
    }

    class NotFound(Exception):
        def __init__(self):
            self.response = {'Error': {'Code': '404'}}

    def fake_head(Bucket, Key):
        raise NotFound()

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_handler.validate') as mock_validate:
        s3 = MagicMock()
        s3.head_object.side_effect = fake_head
        mock_client.return_value = s3
        result = lambda_handler(event, None)

    mock_validate.assert_not_called()
    assert result == {'success': False, 'error': 'Missing label or EDI file'}
