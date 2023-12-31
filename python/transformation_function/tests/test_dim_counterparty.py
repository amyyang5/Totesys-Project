import pytest
import pandas as pd
import boto3
from moto import mock_s3
from python.transformation_function.src.dim_counterparty import (
    dim_counterparty_data_frame, create_and_push_parquet, main)
import tempfile
# Set up the mock S3 environment and create the CSV for testing


@pytest.fixture
def create_mock_s3():
    with mock_s3():
        s3 = boto3.client('s3', region_name='eu-west-2')
        s3.create_bucket(
            Bucket='ingested-data-vox-indicium',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
        s3.create_bucket(
            Bucket='processed-data-vox-indicium',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
        csv_data = """counterparty_id,counterparty_legal_name,legal_address_id,commercial_contact,delivery_contact,created_at,last_updated\n1,Fahey and Sons,15,Micheal Toy,Mrs. Lucy Runolfsdottir,2022-11-03 14:20:51.563000,2022-11-03 14:20:51.563000\n"""  # noqa: E501
        csv_data2 = """address_id,address_line_1,address_line_2,district,city,postal_code,country,phone,created_at,last_updated\n1,6826 Herzog Via,,Avon,New Patienceburgh,28441,Turkey,1803 637401,2022-11-03 14:20:49.962000,2022-11-03 14:20:49.962000"""  # noqa: E501
        s3.put_object(Bucket='ingested-data-vox-indicium',
                      Key='counterparty.csv', Body=csv_data)
        s3.put_object(Bucket='ingested-data-vox-indicium',
                      Key='address.csv', Body=csv_data2)
        yield
# Test the dim_counterparty_data_frame function


def test_dim_counterparty_data_frame(create_mock_s3):
    result = dim_counterparty_data_frame('counterparty', 'address')
    print(result)
    assert isinstance(result, pd.DataFrame)


def test_dim_counterparty_data_frame_invalid_table_name_type_error():
    with pytest.raises(TypeError):
        dim_counterparty_data_frame(123)


def test_dim_counterparty_data_frame_file_not_found_error(create_mock_s3):
    with pytest.raises(ValueError):
        dim_counterparty_data_frame('non_existent_file', 'address')
# Test error for empty table name


def test_dim_counterparty_data_frame_empty_table_name_error():
    with pytest.raises(ValueError):
        dim_counterparty_data_frame('', 'address')
# Test the create_and_push_parquet function


def test_if_the_parquet_file_was_created_in_the_process_bucket(create_mock_s3):
    df = pd.DataFrame({'dummy': [1]})
    create_and_push_parquet(df, 'dim_counterparty')
    s3 = boto3.client('s3', region_name='eu-west-2')
    # Check if the file was created in the S3 bucket
    response = s3.get_object(
        Bucket='processed-data-vox-indicium', Key='dim_counterparty.parquet')
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200


def test_parquet_content_from_process_bucket(create_mock_s3):
    # Create expected DataFrame
    expected_df = pd.DataFrame({
        "counterparty_id": [1],
        "counterparty_legal_name": ["Fahey and Sons"],
        "counterparty_legal_address_line_1": ["6826 Herzog Via"],
        "counterparty_legal_address_line2": [""],
        "counterparty_legal_district": ["Avon"],
        "counterparty_legal_city": ["New Patienceburgh"],
        "counterparty_legal_postal_code": ["28441"],
        "counterparty_legal_country": ["Turkey"],
        "counterparty_legal_phone_number": ["1803 637401"]
    })
    create_and_push_parquet(expected_df, 'dim_counterparty')
    s3 = boto3.client('s3', region_name='eu-west-2')
    # Retrieve the parquet file from S3 bucket
    response = s3.get_object(
        Bucket='processed-data-vox-indicium', Key='dim_counterparty.parquet')
    parquet_file = response['Body'].read()
    # Write the retrieved content to a temporary file
    retrieved_parquet_path = tempfile.mktemp(suffix='.parquet')
    with open(retrieved_parquet_path, 'wb') as temp_file:
        temp_file.write(parquet_file)
    # Read the parquet file with pandas
    read_parquet = pd.read_parquet(retrieved_parquet_path)
    # Compare both DataFrames
    pd.testing.assert_frame_equal(expected_df, read_parquet)
# Test the main function


def test_main(create_mock_s3):
    main()
    # Check if the file was transferred in the final bucket
    s3 = boto3.client('s3', region_name='eu-west-2')
    response = s3.get_object(
        Bucket='processed-data-vox-indicium', Key='dim_counterparty.parquet')
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200
