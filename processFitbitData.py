import boto3
import json
import logging
import base64
import urllib3
import urllib.parse
import datetime
from decimal import Decimal
import os
# import requests

SSM = boto3.client("ssm")
# FITBIT_URL_ENDPOINT will be used to obtain the Fitbit data
FITBIT_URL_ENDPOINT = 'https://api.fitbit.com/1/user/-/profile.json'
# FITBIT_TOKEN_ENDPOINT will be used to obtain new access and refresh tokens
FITBIT_TOKEN_ENDPOINT = "https://api.fitbit.com/oauth2/token"

todays_date = str(datetime.datetime.now().strftime("%Y-%m-%d"))
http = urllib3.PoolManager()
log_level = os.environ.get('LAMBDA_LOG_LEVEL', 'INFO')
logger = logging.getLogger()
logger.setLevel(log_level)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('FitbitData')

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
        # Change (overwrite) the values in parameter store
        SSM.put_parameter(Name=access_param_name, Value=json_response['access_token'], Overwrite=True)
        SSM.put_parameter(Name=refresh_param_name, Value=json_response['refresh_token'], Overwrite=True)

def get_fitbit_data(access_token):

    header = {
        'Authorization': 'Bearer ' + access_token
    }

    
    # Make API calls to retrieve specific data.
    breathing_rate_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/br/date/today.json', headers=header).data.decode("utf-8"))
    water_log_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/foods/log/water/date/today.json', headers=header).data.decode("utf-8"))
    core_temp_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/temp/core/date/today.json', headers=header).data.decode("utf-8"))
    spo2_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/spo2/date/today.json', headers=header).data.decode("utf-8"))
    ecg_readings_summary = json.loads(http.request("GET", 'https://api.fitbit.com/1/user/-/ecg/list.json', headers=header, fields={
        'beforeDate': todays_date,
        'sort': 'desc',
        'limit': 10,
        'offset': 0
    }).data.decode("utf-8"))
    
    # Create Dictionary to store data.
    data = {
        'breathing_rate': breathing_rate_summary, 
        'water_log': water_log_summary, 
        'core_temp': core_temp_summary, 
        'spo2_log': spo2_summary,
        'ecg_log': ecg_readings_summary
    }
    
    return data


# def transform_br_data(data):
#     logger.info({
#         'DataType': 'breathingRate',
#         'timestamp': todays_date,
#         'breathing_rate': data['breathing_rate']['summary']})
#     return {
#         'DataType': 'breathingRate',
#         'timestamp': todays_date,
#         'breathing_rate': data['breathing_rate']['summary']
#       }


# def transform_water_data(data):
#     logger.info({
#         'DataType': 'waterLog',
#         'timestamp': todays_date,
#         'water_log': data['water_log']['summary']['water'] 
#     })
#     return {
#         'DataType': 'waterLog',
#         'timestamp': todays_date,
#         'water_log': data['water_log']['summary']['water'] 
#     }
    

# def transform_core_temp_data(data):
#     logger.info({
#         'DataType': 'tempCore',
#         'timestamp': todays_date,
#         'temperature': data['core_temp']['tempCore']['value']
#     })
#     return {
#         'DataType': 'tempCore',
#         'timestamp': todays_date,
#         'temperature': data['core_temp']['tempCore']['value']
#     }


# def transform_ecg_data(data):
#     logger.info({
#         'DataType': 'ecgLog',
#         'timestamp': todays_date,
#         'averageHeartRate': data['ecg_log']['ecgReadings']['averageHeartRate'],
#         'resultClassification': data['ecg_log']['ecgReadings']['resultClassification']
#     })
#     return {
#         'DataType': 'ecgLog',
#         'timestamp': todays_date,
#         'averageHeartRate': data['ecg_log']['ecgReadings']['averageHeartRate'],
#         'resultClassification': data['ecg_log']['ecgReadings']['resultClassification']
#     }


# def transform_spo2_data(data):
#     logger.info({
#         'DataType': 'spO2',
#         'timestamp': todays_date,
#         'averageSpO2': data['spo2_log']['value']['avg'],
#         'minSpO2': data['spo2_log']['value']['min'],
#         'maxSpO2': data['spo2_log']['value']['max']
#     })
#     return {
#         'DataType': 'spO2',
#         'timestamp': todays_date,
#         'averageSpO2': data['spo2_log']['value']['avg'],
#         'minSpO2': data['spo2_log']['value']['min'],
#         'maxSpO2': data['spo2_log']['value']['max']
#     }

def transform_br_data(data):
    if 'br' in data['breathing_rate'] and len(data['breathing_rate']['br']) > 0:
        logger.info({
            'DataType': 'breathingRate',
            'timestamp': todays_date,
            'breathing_rate': data['breathing_rate']['br'][0]['value']
        })
        return {
            'DataType': 'breathingRate',
            'timestamp': todays_date,
            'breathing_rate': data['breathing_rate']['br'][0]['value']
        }
    else:
        logger.error("No breathing rate data available.")
        return None

def transform_water_data(data):
    if 'summary' in data['water_log'] and 'water' in data['water_log']['summary']:
        logger.info({
            'DataType': 'waterLog',
            'timestamp': todays_date,
            'water_log': data['water_log']['summary']['water']
        })
        return {
            'DataType': 'waterLog',
            'timestamp': todays_date,
            'water_log': data['water_log']['summary']['water']
        }
    else:
        logger.error("No water log data available.")
        return None

def transform_core_temp_data(data):
    if 'tempCore' in data['core_temp'] and len(data['core_temp']['tempCore']) > 0:
        logger.info({
            'DataType': 'tempCore',
            'timestamp': todays_date,
            'temperature': data['core_temp']['tempCore'][0]['value']
        })
        return {
            'DataType': 'tempCore',
            'timestamp': todays_date,
            'temperature': data['core_temp']['tempCore'][0]['value']
        }
    else:
        logger.error("No core temperature data available.")
        return None

def transform_ecg_data(data):
    if 'ecgReadings' in data['ecg_log'] and len(data['ecg_log']['ecgReadings']) > 0:
        logger.info({
            'DataType': 'ecgLog',
            'timestamp': todays_date,
            'averageHeartRate': data['ecg_log']['ecgReadings'][0]['averageHeartRate'],
            'resultClassification': data['ecg_log']['ecgReadings'][0]['resultClassification']
        })
        return {
            'DataType': 'ecgLog',
            'timestamp': todays_date,
            'averageHeartRate': data['ecg_log']['ecgReadings'][0]['averageHeartRate'],
            'resultClassification': data['ecg_log']['ecgReadings'][0]['resultClassification']
        }
    else:
        logger.error("No ECG data available.")
        return None

def transform_spo2_data(data):
    if 'value' in data['spo2_log']:
        logger.info({
            'DataType': 'spO2',
            'timestamp': todays_date,
            'averageSpO2': data['spo2_log']['value']['avg'],
            'minSpO2': data['spo2_log']['value']['min'],
            'maxSpO2': data['spo2_log']['value']['max']
        })
        return {
            'DataType': 'spO2',
            'timestamp': todays_date,
            'averageSpO2': data['spo2_log']['value']['avg'],
            'minSpO2': data['spo2_log']['value']['min'],
            'maxSpO2': data['spo2_log']['value']['max']
        }
    else:
        logger.error("No SpO2 data available.")
        return None


# def add_data_dyanamodb(data):
#     transformed_data = []
#     transformed_data.append(transform_br_data(data))
#     transformed_data.append(transform_water_data(data))
#     transformed_data.append(transform_core_temp_data(data))
#     transformed_data.append(transform_ecg_data(data))
#     transformed_data.append(transform_spo2_data(data))
    
#     for item in transformed_data:
#         try:
#             table.put_item(Item=item)
#             logger.info(f"Item placed in DynamoDB Table: {item}")
#         except Exception as e:
#             logger.error(f'An error occured when attempting to place item in Table: {e}')


def add_data_dyanamodb(data):
    transformed_data = []
    br_data = transform_br_data(data)
    if br_data:
        transformed_data.append(br_data)
    
    water_data = transform_water_data(data)
    if water_data:
        transformed_data.append(water_data)
    
    core_temp_data = transform_core_temp_data(data)
    if core_temp_data:
        transformed_data.append(core_temp_data)
    
    ecg_data = transform_ecg_data(data)
    if ecg_data:
        transformed_data.append(ecg_data)
    
    spo2_data = transform_spo2_data(data)
    if spo2_data:
        transformed_data.append(spo2_data)
    
    for item in transformed_data:
        try:
            # Convert numerical values to Decimal
            if 'breathing_rate' in item:
                rounded_br = round(item['breathing_rate'], 2)
                item['breathing_rate'] = rounded_br
                logger.info(item['breathing_rate'])
            elif 'temperature' in item:
                rounded_temp = round(item['temperature'], 2)
                item['temperature'] = rounded_temp
                logger.info(item['temperature'])
            elif 'averageSpO2' in item:
                rounded_avg_spO2 = round(item['averagespO2'], 2)
                rounded_min_spO2 = round(item['minSpO2'], 2)
                rounded_max_spO2 = round(item['maxSpO2'], 2)
                item['averageSpO2'] = rounded_avg_spO2
                item['minSpO2'] = rounded_min_spO2
                item['maxSpO2'] = rounded_max_spO2
                logger.info(item['averageSpO2'])
                logger.info(item['minSpO2'])
                logger.info(item['maxSpO2'])
            
            table.put_item(Item=item)
            logger.info(f"Item placed in DynamoDB Table: {item}")
        except Exception as e:
            logger.error(f'An error occured when attempting to place item ({item}) in Table: {e}')



def lambda_handler(event, context):
    print(event)
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
        add_data_dyanamodb(fitbit_data)
    except Exception as e:
        logger.error("An error occured: {}".format(e))

    
    
    

    
    
