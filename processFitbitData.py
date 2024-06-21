import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb_client = boto3.client('dynamodb')
def lambda_handler(event, context):
    logger.info("Recieved Event:", json.dumps(event))