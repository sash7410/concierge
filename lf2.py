import json
import pandas as pd
import requests
from datetime import datetime
from decimal import Decimal
import boto3


def get_yelp_data(cuisines, location, search_limit=50):
    api_key = 'your_api_key_here'
    headers = {'Authorization': 'Bearer {}'.format(api_key)}
    url = 'https://api.yelp.com/v3/businesses/search'

    all_responses = [[] for _ in cuisines]

    for idx, cuisine in enumerate(cuisines):
        print(f'Gathering Data for {cuisine}')

        for offset in range(0, 80 * search_limit, search_limit):
            params = {
                'location': location,
                'term': f"{cuisine} Restaurants",
                'limit': search_limit,
                'offset': offset,
                'categories': '(restaurants)',
                'sort_by': 'distance'
            }

            response = requests.get(url, headers=headers, params=params)
            all_responses[idx].append(response)

    return all_responses


def create_dataframe(all_responses, cuisines):
    df_list = []

    for idx, cuisine in enumerate(cuisines):
        for response in all_responses[idx]:
            if 'businesses' in response.json():
                df_temp = pd.DataFrame.from_dict(response.json()['businesses'])
                df_temp['cuisine'] = cuisine
                df_list.append(df_temp)

    df = pd.concat(df_list, ignore_index=True)
    df.drop_duplicates(subset=['name'], keep='first', inplace=True)
    return df


def save_to_dynamodb(selected_rows):
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('yelp-restaurants')

    for _, row in selected_rows.iterrows():
        coordinates = row['coordinates']
        coordinates = {key: Decimal(str(value)) for key, value in coordinates.items()}

        item = {
            'insertedAtTimestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Business_ID': row['id'],
            'Name': row['name'],
            'Coordinates': coordinates,
            'Review_Count': int(row['review_count']),
            'Rating': Decimal(str(row['rating'])),
            'Address': row['location']['address1'],
            'Cuisine': row['cuisine'],
            'Zip_Code': row['location'].get('zip_code', '')
        }

        table.put_item(Item=item)


def save_to_opensearch(data_array):
    url = 'https://search-restaurants-es-pta45ddtntzo5ysyfs7xp2prye.us-east-1.es.amazonaws.com/restaurants/_doc/'
    username = 'dinebot-user'
    password = 'CCfall2023!'
    headers = {'Content-Type': 'application/json'}

    for idx, data in enumerate(data_array, start=1):
        data_fixed = json.dumps({
            'business_id': data['id'],
            'categories': data['cuisine']
        })

        response = requests.put(url + str(idx), auth=(username, password), data=data_fixed, headers=headers)
        if response.status_code == 200:
            print('Data uploaded successfully.')
        else:
            print(f'Error: {response.status_code} - {response.text}')


def main():
    cuisines = ['Indian', 'Chinese', 'Italian']
    location = 'Manhattan'

    all_responses = get_yelp_data(cuisines, location)
    df = create_dataframe(all_responses, cuisines)

    selected_rows = pd.concat([df[df['cuisine'] == cuisine].head(50) for cuisine in cuisines], ignore_index=True)
    json_list = selected_rows[['id', 'cuisine']].to_dict('records')
    json_string = json.dumps(json_list)

    with open('selected_rows_es.json', 'w') as json_file:
        json_file.write(json_string)

    selected_rows.to_csv('selected_rows.csv')
    selected_rows.to_json('selected_rows.json')

    save_to_dynamodb(selected_rows)

    with open('selected_rows_es.json', 'r') as file:
        data_array = json.load(file)

    save_to_opensearch(data_array)


if __name__ == '__main__':
    main()
