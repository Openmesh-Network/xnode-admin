# Emulates connection to the studio
from flask import Flask, request, jsonify
import json
import sys
app = Flask(__name__)

avg_cpu_usage = float(0)
avg_mem_usage = float(0)
highest_cpu_usage = float(0)
highest_mem_usage = float(0)
messages = []

if len(sys.argv) > 1:
    mock_msg_path = sys.argv[1]
else: 
    mock_msg_path = "mock_studio_message.json"

def read_mock():
    with open(mock_msg_path, "r") as f:
        return f.read()

@app.route('/xnodes/functions/getXnodeServices', methods=['GET'])
def serve_config():
    mockdata =read_mock()
    print(mockdata)
    return(mockdata)

@app.route('/xnodes/functions/pushXnodeHeartbeat', methods=['POST'])
def post_metrics():
    metric_data = json.loads(request.data)
    print(metric_data)
    messages = metric_data # store in memory to return to read_metrics
    return jsonify(messages)


@app.route('/xnodes/functions', methods=['GET']) # Purely for testing, these metrics should be stored by the endpoint.
def read_metrics():
    return jsonify(messages)


app.run()