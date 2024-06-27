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
def refresh_access_token(client_id, client_secret, refresh_token, access_param_name, refresh_param_name):
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
    
    try:
        return json_response
    except Exception as e:
        logger.error("An error occured when attempting to refresh tokens: {}".format(e))
    finally:
        logger.info(f"Old access token: {get_parameter("Fitbit_Access_Token", True)}")
        logger.info(f"Old refresh token: {get_parameter("Fitbit_Refresh_Token", True)}")
        # Change (overwrite) the values in parameter store

        logger.info(json_response)

        # SSM.put_parameter(Name=access_param_name, Value=json_response['access_token'], Overwrite=True)
        # SSM.put_parameter(Name=refresh_param_name, Value=json_response['refresh_token'], Overwrite=True)
        # logger.info(f"New access token: {get_parameter("Fitbit_Access_Token", True)}")
        # logger.info(f"New refresh token: {get_parameter("Fitbit_Refresh_Token", True)}")
 




def get_parameter(parameter_key, decryption_choice):
    parameter = SSM.get_parameter(Name=parameter_key, WithDecryption=decryption_choice)['Parameter']['Value']
    return parameter

# get_fitbit_data function works
def get_fitbit_data(access_token):
    header = {
        'Authorization': 'Bearer ' + access_token
    }
    response = http.request("GET", FITBIT_URL_ENDPOINT, headers=header).data.decode("utf-8")
    return json.dumps(response)

def lambda_handler(event, context):
    client_id_parameter = get_parameter("Fitbit_Client_ID", True)
    client_secret_parameter = get_parameter("Fitbit_Client_Secret", True)
    refresh_token_parameter = get_parameter("Fitbit_Refresh_Token", True)
    ACCESS_PARAMETER_NAME = "Fitbit_Access_Token"
    REFRESH_PARAMETER_NAME = "Fitbit_Refresh_Token"
    refresh_access_token(client_id_parameter, client_secret_parameter, refresh_token_parameter, ACCESS_PARAMETER_NAME, REFRESH_PARAMETER_NAME)
