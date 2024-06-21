from flask import Flask, render_template, jsonify, request
import networkx as nx
from pyvis.network import Network
import json

# Import the functions from your tessel4.py module
from tessel4 import build_concept_graph, prompt_lm

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/initial_graph')
def initial_graph():
    # Get concepts from query parameters, use defaults if not provided
    concept1 = request.args.get('concept1', 'Artificial Intelligence')
    concept2 = request.args.get('concept2', 'Natural Intelligence')
    
    graph = build_concept_graph(concept1, concept2, max_depth=1)
    return json_graph(graph)

@app.route('/expand_node', methods=['POST'])
def expand_node():
    data = request.json
    node = data['node']
    current_graph = nx.node_link_graph(data['graph'])
    
    connected_nodes = list(current_graph.neighbors(node))
    
    if len(connected_nodes) > 0:
        new_graph = build_concept_graph(node, connected_nodes[0], max_depth=1, graph=current_graph)
    else:
        opposing_concept = prompt_lm(f"Provide an opposing concept to {node}")
        new_graph = build_concept_graph(node, opposing_concept, max_depth=1, graph=current_graph)
    
    return json_graph(new_graph)

def json_graph(graph):
    return jsonify(nx.node_link_data(graph))

if __name__ == '__main__':
    app.run(debug=True)