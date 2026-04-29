import requests


def verify_facebook_token(access_token: str) -> dict:
    response = requests.get(
        'https://graph.facebook.com/me',
        params={'fields': 'id,first_name,last_name,email', 'access_token': access_token},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValueError('Invalid Facebook token.')
    data = response.json()
    if 'error' in data:
        raise ValueError(data['error'].get('message', 'Invalid Facebook token.'))
    if not data.get('email'):
        raise ValueError('Facebook account does not have a public email. Please use email registration.')
    return {
        'email': data['email'],
        'first_name': data.get('first_name', ''),
        'last_name': data.get('last_name', ''),
        'facebook_id': data.get('id', ''),
    }
