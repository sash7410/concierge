import json
import os
import boto3
import re
import json
import datetime
import time
import os
import dateutil.parser
from datetime import datetime
import logging
from utils import *

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Initialize SQS client
sqs = boto3.client('sqs')

# SQS Queue URL
queue_url = 'https://sqs.us-east-1.amazonaws.com/466579977483/newLex'


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }

def send_sqs_message(slots):
    # Prepare the message
    message_attributes = {
        'Location': {'StringValue': slots['Location'], 'DataType': 'String'},
        'Cuisine': {'StringValue': slots['Cuisine'], 'DataType': 'String'},
        'DiningTime': {'StringValue': slots['DiningTime'], 'DataType': 'String'},
        'NumberOfPeople': {'StringValue': str(slots['NumPeople']), 'DataType': 'Number'},
        'Email': {'StringValue': slots['Email'], 'DataType': 'String'}
    }

    # Send message to SQS queue
    sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes=message_attributes,
        MessageBody=json.dumps(message_attributes)
    )

def confirm_intent(intent_name, slots, message):
    return {
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': {
                'contentType': 'PlainText',
                'content': message
            }
        }
    }

# Main Handlers
def handle_greeting_intent(session_attributes):
    return {
        "sessionAttributes": session_attributes,
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                "contentType": "PlainText",
                "content": "Hi there, how can I help?"
            }
        }
    }


def handle_thank_you_intent(session_attributes):
    return {
        "sessionAttributes": session_attributes,
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                "contentType": "PlainText",
                "content": "You're welcome! If you have any more questions, feel free to ask."
            }
        }
    }

def dispatch(intent_request):
    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))
    intent_name = intent_request['currentIntent']['name']
    if intent_name == 'Iwanttohavesomefood':
        return find_food(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')

def lambda_handler(event, context):
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

        # Check if the user's input matches a greeting phrase
    if event['inputTranscript'] in ['hello', 'hi', 'hey']:
        return {
            'sessionAttributes': event['sessionAttributes'],
            'dialogAction': {
                'type': 'ElicitIntent',
                'message': {
                    'contentType': 'PlainText',
                    'content': 'Hello! I noticed you might be hungry. How can I assist you with food?'
                }
            }
        }
        # Add other logic for the intent here

    return dispatch(event)
# Lambda Handler



def find_food(intent_request):
    slots = try_ex(lambda: intent_request['currentIntent']['slots'])
    location = try_ex(lambda: slots['Location'])
    cuisine = try_ex(lambda: slots['Cuisine'])
    dining_time = try_ex(lambda: slots['DiningTime'])
    number_of_people = safe_int(try_ex(lambda: slots['NumPeople']))
    email = try_ex(lambda: slots['Email'])

    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    # Load food history and track the current findings.
    reservation = json.dumps({
        'Location': location,
        'NumPeople': number_of_people,
        'Cuisine': cuisine,
        'DiningTime': dining_time,
        'Email': email
    })
    session_attributes['currentReservation'] = reservation
    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_dining_request(slots)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        session_attributes['currentReservation'] = reservation
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    logger.debug('book reservation under={}'.format(reservation))
    send_sqs_message(slots)

    session_attributes['lastConfirmedReservation'] = reservation

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Your reservation has been successfully made,'
                       ' and an email containing all the details has been sent to you.'
        }
    )
