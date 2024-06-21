import boto3
import json

dynamodb_client = boto3.client('dynamodb')
def lambda_handler(event, context):
    print("testing")