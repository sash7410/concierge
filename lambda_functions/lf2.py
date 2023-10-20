import json
import boto3
from boto3.dynamodb.conditions import Key
import random
import requests

# Initialize clients
ses_client = boto3.client('ses', region_name='us-east-1')
sqs = boto3.client('sqs', region_name='us-east-1')  # Specify the region

# Specify the SQS queue URL
queue_url = 'https://sqs.us-east-1.amazonaws.com/466579977483/newLex'


def send_email(destination, subject, body):
    try:
        ses_client.send_email(
            Destination=destination,
            Message={
                'Body': {'Text': {'Data': body}},
                'Subject': {'Data': subject}
            },
            Source='sr6890@nyu.edu'
        )
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {str(e)}")


def fetch_restaurant_details(restaurant_ids, table_name):
    dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
    table = dynamodb.Table(table_name)
    restaurant_details = []
    for restaurant_id in restaurant_ids:
        response = table.query(
            KeyConditionExpression=Key('Business_ID').eq(restaurant_id)
        )
        items = response.get('Items', [])
        if items:
            restaurant_details.append(items[0])
    return restaurant_details


def perform_elasticsearch_search(input_cuisine):
    es_endpoint = "https://search-restaurants-es-pta45ddtntzo5ysyfs7xp2prye.us-east-1.es.amazonaws.com"
    es_index = "restaurants"
    es_username = "dinebot-user"
    es_password = "CCfall2023!"

    search_query = {
        "query": {
            "bool": {
                "must": [{"match": {"categories": input_cuisine}}],
                "must_not": [],
                "should": []
            }
        },
        "from": 0,
        "size": 50,
        "sort": [],
        "aggs": {}
    }

    search_url = f"{es_endpoint}/{es_index}/_search"

    try:
        response = requests.post(search_url, json=search_query, auth=(es_username, es_password))
        response.raise_for_status()
        data = response.json()
        restaurant_hits = data.get('hits', {}).get('hits', [])
        return restaurant_hits
    except Exception as e:
        print(f"Error making Elasticsearch request: {str(e)}")
        return []


def process_message(message_body):
    input_cuisine = message_body.get("Cuisine", {}).get("StringValue", "")
    email_address = message_body.get("Email", {}).get("StringValue", "")
    dining_time = message_body.get("DiningTime", {}).get("StringValue", "")
    num_people = message_body.get("NumberOfPeople", {}).get("StringValue", "")

    restaurant_hits = perform_elasticsearch_search(input_cuisine)

    if not restaurant_hits:
        return None

    restaurant_ids = [hit['_source']['business_id'] for hit in restaurant_hits]
    random.shuffle(restaurant_ids)
    restaurant_details = fetch_restaurant_details(restaurant_ids[:3], "yelp-restaurants")

    return {
        'input_cuisine': input_cuisine,
        'email_address': email_address,
        'dining_time': dining_time,
        'num_people': num_people,
        'restaurant_details': restaurant_details
    }


def lambda_handler(event, context):
    print("Received event:")
    print(json.dumps(event, indent=2))

    try:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            AttributeNames=['All'],
            MessageAttributeNames=['All'],
            MaxNumberOfMessages=10,
            VisibilityTimeout=30,
            WaitTimeSeconds=0
        )
    except Exception as e:
        print(f"Error receiving messages from SQS: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({"error": "Error receiving messages from SQS"})
        }
    finally:
        # Check if there are any messages in the response and delete them
        if 'Messages' in response:
            for message in response['Messages']:
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
    print(response)

    if 'Messages' in response:
        for message in response['Messages']:
            try:
                message_body = json.loads(message['Body'])
                print(f"Received message: {message_body}")

                result = process_message(message_body)

                if result:
                    input_cuisine = result['input_cuisine']
                    email_address = result['email_address']
                    dining_time = result['dining_time']
                    num_people = result['num_people']
                    restaurant_details = result['restaurant_details']

                    email_subject = 'Restaurant Suggestions'
                    email_body = f"Hello! Here are my {input_cuisine} restaurant suggestions for {num_people} people at {dining_time} in {location}:\n"

                    for i, restaurant in enumerate(restaurant_details, start=1):
                        email_body += f"{i}. {restaurant['Name']}, located at {restaurant['Address']}\n"

                    email_body += "Enjoy your meal!"

                    destination = {'ToAddresses': [email_address]}
                    send_email(destination, email_subject, email_body)

                    print("Sending email...")
                    print(f"Subject: {email_subject}")
                    print(f"Body: {email_body}")


                else:
                    print("No restaurant suggestions for this message")

            except Exception as e:
                print(f"Error processing message: {str(e)}")
                continue
    else:
        print("No messages in the queue")

    return {
        'statusCode': 200,
        'body': json.dumps('No messages to process')
    }
