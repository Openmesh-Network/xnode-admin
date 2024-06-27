# Emulates connection to the studio
from flask import Flask, request, jsonify
import json
import sys
import hmac
app = Flask(__name__)

avg_cpu_usage = float(0)
avg_mem_usage = float(0)
highest_cpu_usage = float(0)
highest_mem_usage = float(0)
messages = []
access_token = "Tah6WlMnal0mpka6ki8jHmoD9hhK9KXc81xyNjvSt1hm1nj74dlM4W8jPEdPdmSJD1JVba"

if len(sys.argv) > 1:
    mock_msg_path = sys.argv[1]
else: 
    mock_msg_path = "mock_studio_message.json"

def read_mock():
    with open(mock_msg_path, "r") as f:
        return f.read()

@app.route('/xnodes/functions/getXnodeServices', methods=['GET'])
def serve_config():
    print(request.headers)
    mockdata =read_mock()
    print(mockdata)
    return(mockdata)

@app.route('/xnodes/functions/pushXnodeHeartbeat', methods=['POST'])
def post_metrics():
    print(request.headers)
    metric_data = json.loads(request.data)
    print(metric_data)
    messages = metric_data # store in memory to return to read_metrics
    return jsonify(messages)


@app.route('/xnodes/functions', methods=['GET']) # Purely for testing, these metrics should be stored by the endpoint.
def read_metrics():
    # Curl to manually verify that the messages were received
    return jsonify(messages)

@app.route('/xnodes/validate_hmac', methods=['POST'])
def validate_hmac():
    print("With access token:",access_token)
    verified = None
    if access_token != "":
        msg_hmac = hmac.new(bytes(access_token, 'utf-8'), msg = bytes(json.dumps(request.json), 'utf-8'), digestmod='sha256').hexdigest()
        verified = hmac.compare_digest(msg_hmac, request.headers['X-Parse-Session-Token'])
        print("HMAC", msg_hmac, "verification success:", verified)
    else:
        print("Did not find a stored access token")
        verified = request.headers['x-parse-session-token']
    return jsonify(verified)

app.run(port=5000)