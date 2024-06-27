import requests
import json
import base64
from xnode_admin import utils

uuid = "I5KMFECV11H-VX5K78G4P7I"
access_token = "Tah6WlMnal0mpka6ki8jHmoD9hhK9KXc81xyNjvSt1hm1nj74dlM4W8jPEdPdmSJD1JVba+eDHEceUysRZnplw=="
preshared_key = base64.b64decode(access_token)
local_mock_studio = "http://localhost:3003"

def hmac_test():
    print("Created hmac from token:",access_token)

    message = {
        "id": uuid,
        "other-data":"abcxyz"
    }

    print("output:")
    print(json.dumps(message))
    msg_hmac = utils.generate_hmac(preshared_key, message)
    headers = {
        'x-parse-session-token': msg_hmac
    }
    response = requests.post(local_mock_studio + "/xnodes/validate_hmac", json=message, headers=headers)
    print(response.text)

#hmac_test()

def dpl_test():
    message = {
        "id": uuid,
    }

    print(json.dumps(message).replace(" ", ""))
    msg_hmac = utils.generate_hmac(preshared_key, message)
    headers = {
        'x-parse-session-token': msg_hmac
    }
    print("hmac:", msg_hmac)
    response = requests.get(local_mock_studio + "/xnodes/functions/getXnodeServices", json=message, headers=headers)
    print(response.text)
    #print(response.json)

dpl_test()
