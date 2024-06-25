import boto3
import json
import logging
import base64
import urllib3
import urllib.parse

SSM = boto3.client("ssm")
# FITBIT_URL_ENDPOINT will be used to obtain the Fitbit data
FITBIT_URL_ENDPOINT = 'https://api.fitbit.com/1/user/-/profile.json'
# FITBIT_TOKEN_ENDPOINT will be used to obtain new access and refresh tokens
FITBIT_TOKEN_ENDPOINT = "https://api.fitbit.com/oauth2/token"

http = urllib3.PoolManager()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
dynamodb_client = boto3.client('dynamodb')

# Function should refresh the tokens in Systems Paramter Store
def refresh_access_token(client_id, client_secret, refresh_token):
    concatenated_client_id_client_secret = f"{client_id}:{client_secret}"
    base64_credentials = base64.b64encode(concatenated_client_id_client_secret.encode()).decode()

    myheader = {
        'Authorization': f'Basic {base64_credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    encoded_data = urllib.parse.urlencode(data)
    
    response = http.request("POST", FITBIT_TOKEN_ENDPOINT, headers=myheader, body=encoded_data).data.decode("utf-8")
    
    json_response = json.loads(response)

    return json_response


def get_parameter(parameter_key, decryption_choice):
    parameter = SSM.get_parameter(Name=parameter_key, WithDecryption=decryption_choice)['Parameter']['Value']
    return parameter

def get_fitbit_data(access_token):
    header = {
        'Authorization': 'Bearer ' + access_token
    }
    response = http.request("GET", FITBIT_URL_ENDPOINT, headers=header).data.decode("utf-8")
    return json.dumps(response)

# def append_dyanamodb_table(table, f)

def lambda_handler(event, context):
    client_id_parameter = get_parameter("Fitbit_Client_ID", True)
    client_secret_parameter = get_parameter("Fitbit_Client_Secret", True)
    refresh_token_parameter = get_parameter("Fitbit_Refresh_Token", True)
    token_response = refresh_access_token(client_id_parameter, client_secret_parameter, refresh_token_parameter)
    logger.info("Token response: %s", token_response)
    
    if "access_token" in token_response:
        access_token = token_response["access_token"]
        fitbit_data = get_fitbit_data(access_token)
        logger.info("Fitbit data: %s", fitbit_data)
    else:
        logger.error("Failed to refresh token: %s", token_response)
    
    logger.info(json.dumps(event))
    
    
    
    
    
    
    
    logger.info(json.dumps(event))



