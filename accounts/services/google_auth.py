import requests


def verify_google_token(access_token: str) -> dict:
    response = requests.get(
        'https://www.googleapis.com/oauth2/v3/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValueError('Invalid Google token.')
    data = response.json()
    if not data.get('email'):
        raise ValueError('Google token does not contain an email address.')
    return {
        'email': data['email'],
        'first_name': data.get('given_name', ''),
        'last_name': data.get('family_name', ''),
        'google_id': data.get('sub', ''),
    }
