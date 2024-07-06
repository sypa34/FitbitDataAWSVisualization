import boto3
import json
import logging
import base64
import urllib3
import urllib.parse
import datetime
# import requests

SSM = boto3.client("ssm")
# FITBIT_URL_ENDPOINT will be used to obtain the Fitbit data
FITBIT_URL_ENDPOINT = 'https://api.fitbit.com/1/user/-/profile.json'
# FITBIT_TOKEN_ENDPOINT will be used to obtain new access and refresh tokens
FITBIT_TOKEN_ENDPOINT = "https://api.fitbit.com/oauth2/token"

todays_date = str(datetime.datetime.now())
http = urllib3.PoolManager()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
dynamodb_client = boto3.client('dynamodb')
# table = dynamodb_client.Table('FitbitData')

def verify_subscriber(event, context):
    
    CORRECT_VERIFICATION_CODE = "50ac9687637e30631ee449024a176e10953c8f03627160c4fd4ba55114c7008c"
    # Get the 'verify' query string parameter
    verify_param = event['queryStringParameters'].get('verify', '')

    # Check if the verification code is correct
    if verify_param == CORRECT_VERIFICATION_CODE:
        # Return a 204 No Content response for the correct verification code
        return {
            'statusCode': 204,
            'body': ''
        }
    else:
        # Return a 404 Not Found response for an incorrect verification code
        return {
            'statusCode': 404,
            'body': ''
        }

def create_subscription(access_token, subscription_id, collection_path=None):
    http = urllib3.PoolManager()
    base_url = "https://api.fitbit.com/1/user/-"
    if collection_path:
        url = f"{base_url}/{collection_path}/apiSubscriptions/{subscription_id}.json"
    else:
        url = f"{base_url}/apiSubscriptions/{subscription_id}.json"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Length": "0",
        "Content-Type": "application/json"
    }

    response = http.request("POST", url, headers=headers)
    response_data = json.loads(response.data.decode("utf-8"))

    if response.status == 201:
        logger.info("Subscription created successfully!!!!")
    elif response.status == 200:
        logger.error("Subscription already exists with the same subscription ID.")
    elif response.status == 409:
        logger.error("Conflict: Subscription ID is already used for a different stream.")
    else:
        logger.error(f"Failed to create subscription: {response.status} - {response_data}")

    return response_data

def get_parameter(parameter_key, decryption_choice):
    parameter = SSM.get_parameter(Name=parameter_key, WithDecryption=decryption_choice)['Parameter']['Value']
    return parameter

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
        # Try to send POST message to Fitbit API
        return json_response
    except Exception as e:
        logger.error("An error occured when attempting to refresh tokens: {}".format(e))
    finally:
        logger.info(f"Old access token: {get_parameter("Fitbit_Access_Token", True)}")
        logger.info(f"Old refresh token: {get_parameter("Fitbit_Refresh_Token", True)}")
        # Log the Fitbit API response to Cloudwatch
        logger.info(f"Fitbit API Response: {json_response}")
        # Change (overwrite) the values in parameter store
        SSM.put_parameter(Name=access_param_name, Value=json_response['access_token'], Overwrite=True)
        SSM.put_parameter(Name=refresh_param_name, Value=json_response['refresh_token'], Overwrite=True)
        # Log the New Access Tokens updated in Parameter Store to Cloudwatch
        logger.info(f"New access token: {get_parameter("Fitbit_Access_Token", True)}")
        logger.info(f"New refresh token: {get_parameter("Fitbit_Refresh_Token", True)}")
 
def get_fitbit_data(access_token):

    header = {
        'Authorization': 'Bearer ' + access_token
    }

    # ******Ignore for now:
    # ecg_readings_summary = http.request("GET", 'https://api.fitbit.com/1/user/-/ecg/list.json', headers=header, params={'beforeDate': todays_date,
    #     'sort': 'desc',
    #     'limit': 10,
    #     'offset': 0
    # }).data.decode("utf-8")

    
    # Make API calls to retrieve specific data.
    breathing_rate_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/br/date/today.json', headers=header).data.decode("utf-8"))
    water_log_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/foods/log/water/date/today.json', headers=header).data.decode("utf-8"))
    core_temp_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/temp/core/date/today.json', headers=header).data.decode("utf-8"))
    spo2_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/spo2/date/today.json', headers=header).data.decode("utf-8"))
    
    # Create Dictionary to store data.
    data = {
        'breathing_rate': breathing_rate_summary, 
        'water_log': water_log_summary, 
        'core_temp': core_temp_summary, 
        'spo2_log': spo2_summary
    }
    
    # Log the retreived data.
    logger.info(f"Breathing Rate: {breathing_rate_summary}")
    # logger.info(f"ECG Readings: {ecg_readings_summary}")
    logger.info(f"Water Log: {water_log_summary}")
    logger.info(f"Core Temperature: {core_temp_summary}")
    logger.info(f"SPO2 Summary: {spo2_summary}")
    logger.info(f"Combined dictionary: {data}")
    return data


def transform_br_data(data):
    return {
        'DataType': 'BreathingRate',
        'timestamp': todays_date,
        'breathing_rate': data['breathing_rate']['summary']
    }


def transform_water_data(data):
    return {
        'DataType': 'WaterLogData',
        'timestamp': todays_date,
        'water_log': data['water_log']['summary']['water'] 
    }
    

# def transform_core_temp_data(data):
#     # add code

# def transform_spo2_data(data):
#     # add code
    

# def add_data_dyanamodb(data):


def lambda_handler(event, context):
    
    logger.debug(event)

    # Get needed parameters for refresh token and declare constant variables
    client_id_parameter = get_parameter("Fitbit_Client_ID", True)
    client_secret_parameter = get_parameter("Fitbit_Client_Secret", True)
    refresh_token_parameter = get_parameter("Fitbit_Refresh_Token", True)
    ACCESS_PARAMETER_NAME = "Fitbit_Access_Token"
    REFRESH_PARAMETER_NAME = "Fitbit_Refresh_Token"
    # Call the refresh_access_token function to refresh the tokens used to obtain Fitbit Data
    refresh_access_token(client_id_parameter, client_secret_parameter, refresh_token_parameter, ACCESS_PARAMETER_NAME, REFRESH_PARAMETER_NAME)
    # Attempt to get the fitbit data
    try: 
        fitbit_data = get_fitbit_data(get_parameter("Fitbit_Access_Token", True))
    except Exception as e:
        logger.error("An error occured when trying to obtain Fitbit Data: {}".format(e))

    
    
    

    
    
