#import Libraries
import geopandas as gpd
import boto3
import botocore
import os
import tempfile

# Initialize an anonymous S3 client
s3 = boto3.client(
    's3',
    config=botocore.config.Config(signature_version=botocore.UNSIGNED)
)

bucket_name = 'sdmlab'
pwb_folder = "PWB/"  

def PWB_inS3(s3_client, bucket, prefix):
    """Download all components of a shapefile from S3 into a temporary directory."""
    tmp_dir = tempfile.mkdtemp()
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' not in response:
        raise ValueError("No files found in the specified S3 folder.")
    
    for obj in response['Contents']:
        file_key = obj['Key']
        file_name = os.path.basename(file_key) 
        if file_name.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
            local_path = os.path.join(tmp_dir, file_name)
            s3_client.download_file(bucket, file_key, local_path)
            
    shp_files = [f for f in os.listdir(tmp_dir) if f.endswith(".shp")]
    if not shp_files:
        raise ValueError("No .shp file found after download.")

    shp_path = os.path.join(tmp_dir, shp_files[0])
    return shp_path

def get_PWB():
    shp_path = PWB_inS3(s3, bucket_name, pwb_folder)
    pwb = gpd.read_file(shp_path)
    return pwb