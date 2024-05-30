# Emulates connection to the studio
from flask import Flask, request, jsonify
import json
app = Flask(__name__)

avg_cpu_usage = float(0)
avg_mem_usage = float(0)
highest_cpu_usage = float(0)
highest_mem_usage = float(0)
messages = []

def read_mock():
    with open("mock_studio_message.json", "r") as f:
        return f.read()

@app.route('/xnode/<uuid>', methods=['GET'])
def serve_config(uuid):
    return(read_mock())

@app.route('/xnode/<uuid>/post_metrics', methods=['POST'])
def post_metrics(uuid):
    metric_data = json.loads(request.data)
    print(metric_data)
    messages = metric_data # store in memory to return to read_metrics
    return jsonify(messages)


@app.route('/read_metrics', methods=['GET']) # Purely for testing, these metrics should be stored by the endpoint.
def read_metrics():
    return jsonify(messages)


app.run()