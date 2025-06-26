import json
import sys
from unittest.mock import patch, MagicMock

sys.modules.setdefault('boto3', MagicMock())

from asn_validator.lambda_function import lambda_handler


def test_lambda_handler_triggers_validate(tmp_path):
    label_content = b'L'
    edi_content = b'E'

    def fake_download(bucket, key, filename):
        data = label_content if key == 'labels/a.pdf' else edi_content
        with open(filename, 'wb') as f:
            f.write(data)

    event = {
        'Records': [
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'edi/a.edi'}}},
        ]
    }

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_function.validate') as mock_validate:
        s3 = MagicMock()
        s3.download_file.side_effect = fake_download
        mock_client.return_value = s3
        mock_validate.return_value = {'ok': True}
        result = lambda_handler(event, None)

    mock_validate.assert_called_once()
    assert result == {'ok': True}


def test_lambda_handler_event_without_edi(tmp_path):
    event = {
        'Records': [
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'labels/a.pdf'}}},
        ]
    }

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_function.validate') as mock_validate:
        mock_client.return_value = MagicMock()
        result = lambda_handler(event, None)

    mock_validate.assert_not_called()
    assert result == {'success': False, 'error': 'No EDI file in event'}


def test_lambda_handler_missing_companion(tmp_path):
    event = {
        'Records': [
            {'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'edi/a.edi'}}},
        ]
    }

    class NotFound(Exception):
        def __init__(self):
            self.response = {'Error': {'Code': '404'}}

    def fake_head(Bucket, Key):
        raise NotFound()

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_function.validate') as mock_validate:
        s3 = MagicMock()
        s3.head_object.side_effect = fake_head
        mock_client.return_value = s3
        result = lambda_handler(event, None)

    mock_validate.assert_not_called()
    assert result == {'success': False, 'error': 'Missing label file'}


def test_lambda_handler_nested_prefix(tmp_path):
    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'b'},
                    'object': {
                        'key': '59366/2025/06/26/SH0433920/edi/SH0433920.txt'
                    },
                }
            },
        ]
    }

    def fake_head(Bucket, Key):
        if Key == (
            '59366/2025/06/26/SH0433920/labels/SH0433920.pdf'
        ):
            return {}
        raise Exception({'Error': {'Code': '404'}})

    def fake_download(bucket, key, filename):
        with open(filename, 'wb') as f:
            f.write(b'X')

    with patch('boto3.client') as mock_client, \
         patch('asn_validator.lambda_function.validate') as mock_validate:
        s3 = MagicMock()
        s3.head_object.side_effect = fake_head
        s3.download_file.side_effect = fake_download
        mock_client.return_value = s3
        mock_validate.return_value = {'ok': True}
        result = lambda_handler(event, None)

    mock_validate.assert_called_once()
    assert result == {'ok': True}


