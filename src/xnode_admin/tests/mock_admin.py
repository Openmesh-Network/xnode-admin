import requests
import hmac
import json

uuid = "I5KMFECV11H-VX5K78G4P7I"
access_token = "Tah6WlMnal0mpka6ki8jHmoD9hhK9KXc81xyNjvSt1hm1nj74dlM4W8jPEdPdmSJD1JVba"
local_mock_studio = "http://localhost:5001"

def hmac_test(access_token):
    print("Created hmac from token:",access_token)

    message = {
        "id": uuid,
        "other-data":"abcxyz"
    }
    msg_hmac = hmac.new(bytes(access_token, 'utf-8'), msg = bytes(json.dumps(message), 'utf-8'), digestmod='sha256').hexdigest()
    headers = {
        'x-parse-session-token': msg_hmac
    }
    response = requests.post(local_mock_studio + "/xnodes/validate_hmac", json=message, headers=headers)
    print(response.text)

hmac_test(access_token)