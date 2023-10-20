import json
import os
import boto3
import re
import json
from datetime import datetime
import time
import os
import dateutil.parser
import logging
from utils import *

# --- Helpers that build all of the responses ---

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }

def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_city(location):
    location_types = ['manhattan', 'new york', 'ny', 'nyc']
    return location.lower() in location_types

def isvalid_cuisine(cuisine):
    cuisine_types = ['chinese', 'indian', 'italian']
    return cuisine.lower() in cuisine_types


def is_valid_time(time_str):
    try:
        # Parse the time string to a datetime object
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        # Define the time range for 9 AM and 11 PM
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("23:00", "%H:%M").time()

        # Check if the time falls within the range
        if start_time <= time_obj <= end_time:
            return True
        else:
            return False
    except ValueError:
        return False  # Invalid time format


def isvalid_email(email):
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return False
    return True


def validate_dining_request(slots):
    location = try_ex(lambda: slots['Location'])
    cuisine = try_ex(lambda: slots['Cuisine'])
    dining_time = try_ex(lambda: slots['DiningTime'])
    number_of_people = safe_int(try_ex(lambda: slots['NumPeople']))
    email = try_ex(lambda: slots['Email'])
    if location and not isvalid_city(location):
        return build_validation_result(
            False,
            'Location',
            'We currently do not support {} as a valid destination.  Can you try a different city?'.format(location)
        )
    if dining_time:
        if not is_valid_time(dining_time):
            return build_validation_result(False, 'DiningTime', 'The time should be between 9 AM and 11 PM.')

    if cuisine and not isvalid_cuisine(cuisine):
            return build_validation_result(False, 'Cuisine',
                                           'I did not understand your Cuisine.  What would you like to eat?')

    if number_of_people is not None and (number_of_people < 1 or number_of_people > 20):
        return build_validation_result(
            False,
            'NumPeople',
            'You can make a reservations for from one to twenty nights.  How many people would you to reserve a table for?'
        )

    if email and not isvalid_email(email):
        return build_validation_result(False, 'Email', 'The email address is not valid.')
    return {'isValid': True}


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None

