import json
import boto3

client = boto3.client('lex-runtime')

def lambda_handler(event, context):
    print("event type:", type(event))
    print("event keys:", event.keys())
    # input = event['body']['messages']
    input = event['messages']
    print(input)

    client_request = input[0]['unstructured']['text']
    print("Client message:", client_request)
    # frontend js sends user_id as the last message in messages
    user_id = input[-1]['unstructured']['text']
    print("User id:", user_id)
    
    bot_response = client.post_text(
        botName = 'diningConcierge',
        botAlias = 'lex',
        userId = user_id,
        inputText = client_request
    )
    
    bot_message = bot_response['message'].strip()
    print(bot_message)
    output = json.dumps({"unstructured": {"text": bot_message}})
    
    return {
        "statusCode": 200,
        "messages": [output]
    }
