# pip install openai
# pip install graphviz
print("starting")

import openai
import json
from graphviz import Digraph
import collections

# Set up OpenAI API key
openai.api_key = "none"
openai.api_base = "http://localhost:1234/v1"
#client = openai(base_url="http://localhost:1234/v1", api_key="not-needed")
def prompt_lm(prompt):
    print("inside")
    completion =     response = openai.ChatCompletion.create(model="local_model", 
      messages=[
        {"role": "system", "content": "Employ concepts as poles on an axis to find their perpendicular partners in a tessellating graph function for exploring concept spaces."},
        {"role": "user", "content": prompt}
      ],
      temperature=0.17,
      )
    print(completion)

    return [choice.text.strip() for choice in completion.choices]

def generate_graph():
    initial_subject = "Artificial Intelligence"
    opposite_subject = prompt_lm(f"Suggest an idea that contrasts or opposes the concept of {initial_subject}")[0]

    subject_queue = [initial_subject, opposite_subject]
    graph = Digraph()
    graph.node(initial_subject)
    graph.node(opposite_subject)
    graph.edge(initial_subject, opposite_subject)

    while subject_queue:
        current_subject_a, current_subject_b = subject_queue.pop(0), subject_queue.pop(0)
        prompt = f"Suggest ideas that are perpendicular to the axis formed by '{current_subject_a}' and '{current_subject_b}'"
        new_subjects = prompt_lm(prompt)
        perpendicular_subjects = [s for s in new_subjects if s not in graph.body]
        subject_queue.extend(perpendicular_subjects)
        for new_subject in perpendicular_subjects:
            graph.node(new_subject)
            graph.edge(current_subject_a, new_subject)
            graph.edge(current_subject_b, new_subject)

    return graph

def generate_graph2_null(initial_subject, opposite_subject, max_depth=2):
    graph = Digraph()
    graph.node(initial_subject)
    graph.node(opposite_subject)
    graph.edge(initial_subject, opposite_subject)

    subject_queue = [(initial_subject, opposite_subject, 0)]

    while subject_queue:
        current_subjects, depth = subject_queue.pop(0)[0:2], subject_queue.pop(0)[2]
        if depth >= max_depth:
            continue

        prompt = f"Suggest ideas that are perpendicular to the axis formed by '{current_subjects[0]}' and '{current_subjects[1]}'"
        new_subjects = prompt_lm(prompt)
        perpendicular_subjects = [s for s in new_subjects if s not in graph.body]

        for new_subject in perpendicular_subjects:
            graph.node(new_subject)
            for current_subject in current_subjects:
                graph.edge(current_subject, new_subject)

        for i in range(0, len(perpendicular_subjects), 2):
            if i + 1 < len(perpendicular_subjects):
                new_axis = (perpendicular_subjects[i], perpendicular_subjects[i + 1])
                subject_queue.append((new_axis, depth + 1))

    return graph

def generate_graph2(initial_subject, opposite_subject, max_depth=2):
    graph = Digraph()
    graph.node(initial_subject)
    graph.node(opposite_subject)
    graph.edge(initial_subject, opposite_subject)

    subject_queue = [(initial_subject, opposite_subject, 0)]

    while subject_queue:
        try:
            current_subjects, depth = subject_queue.pop(0)[0:2], subject_queue.pop(0)[2]
        except IndexError:
            break  # Exit the loop if the queue is empty

        if depth >= max_depth:
            continue

        prompt = f"Suggest ideas that are perpendicular to the axis formed by '{current_subjects[0]}' and '{current_subjects[1]}'"
        print(prompt)
        new_subjects = prompt_lm(prompt)
        perpendicular_subjects = [s for s in new_subjects if s not in graph.body]

        if not perpendicular_subjects:
            continue  # Skip this iteration if no new perpendicular subjects are generated

        for new_subject in perpendicular_subjects:
            graph.node(new_subject)
            for current_subject in current_subjects:
                graph.edge(current_subject, new_subject)

        for i in range(0, len(perpendicular_subjects), 2):
            if i + 1 < len(perpendicular_subjects):
                new_axis = (perpendicular_subjects[i], perpendicular_subjects[i + 1])
                subject_queue.append((new_axis, depth + 1))
                 

    return graph

def generate_graph3(initial_subject, opposite_subject, max_depth=2):
    graph = Digraph()
    graph.node(initial_subject)
    graph.node(opposite_subject)
    graph.edge(initial_subject, opposite_subject)

    subject_queue = [(initial_subject, opposite_subject, 0)]

    while subject_queue:
        print(subject_queue)
        current_subjects, depth = subject_queue.pop(0)

        if depth >= max_depth:
            continue

        prompt = f"Suggest ideas that are perpendicular to the axis formed by '{current_subjects[0]}' and '{current_subjects[1]}'"
        print(prompt)  # This line should now be reached
        new_subjects = prompt_lm(prompt)
        perpendicular_subjects = [s for s in new_subjects if s not in graph.body]

        if not perpendicular_subjects:
            continue  # Skip this iteration if no new perpendicular subjects are generated

        for new_subject in perpendicular_subjects:
            graph.node(new_subject)
            for current_subject in current_subjects:
                graph.edge(current_subject, new_subject)

        for i in range(0, len(perpendicular_subjects), 2):
            if i + 1 < len(perpendicular_subjects):
                new_axis = (perpendicular_subjects[i], perpendicular_subjects[i + 1])
                #subject_queue.append(new_axis + (depth + 1,))
                subject_queue.append((new_axis, depth + 1))

    return graph

def generate_graph4(initial_subject, opposite_subject, max_depth=2):
    graph = Digraph()
    graph.node(initial_subject)
    graph.node(opposite_subject)
    graph.edge(initial_subject, opposite_subject)

    subject_queue = [(initial_subject, opposite_subject, 0)]

    while subject_queue:
        #current_subject, depth = subject_queue.pop(0)
        depth, current_subject = subject_queue.pop(0)[0:2]

        if int(depth) >= max_depth:
        #if int(depth.split()[0]) >= max_depth: #didn't work
            continue

        prompt = f"Suggest ideas that are perpendicular to the axis formed by '{current_subjects[0]}' and '{current_subjects[1]}'"
        print(prompt)  # This line should now be reached
        new_subjects = prompt_lm(prompt)
        perpendicular_subjects = [s for s in new_subjects if s not in graph.body]

        if not perpendicular_subjects:
            continue  # Skip this iteration if no new perpendicular subjects are generated

        for new_subject in perpendicular_subjects:
            graph.node(new_subject)
            for current_subject in current_subjects:
                graph.edge(current_subject, new_subject)

        for i in range(0, len(perpendicular_subjects), 2):
            if i + 1 < len(perpendicular_subjects):
                new_axis = (perpendicular_subjects[i], perpendicular_subjects[i + 1])
                subject_queue.append((new_axis, depth + 1))

    return graph

from collections import namedtuple
from collections import deque  # Import for queue functionality

SubjectEntry = namedtuple("SubjectEntry", ["subject", "depth"])


def generate_graph5(initial_subject, opposite_subject, max_depth=2):
    graph = Digraph()
    graph.node(initial_subject)
    graph.node(opposite_subject)
    graph.edge(initial_subject, opposite_subject)

    subject_queue = deque([SubjectEntry(initial_subject, 0), SubjectEntry(opposite_subject, 0)])

    while subject_queue:
        subject_entry = subject_queue.popleft()  # Use popleft() for queue behavior

        if subject_entry.depth >= max_depth:
            continue

        #prompt = f"Suggest ideas that are perpendicular to the axis formed by '{subject_entry.subject[0:]}' and '{subject_entry.subject[1:]}'"
        #subject1, subject2 = subject_entry.subject
        #prompt = f"Suggest ideas that are perpendicular to the axis formed by '{subject1}' and '{subject2}'"
        prompt = f"Suggest ideas that are perpendicular to the axis formed by '{subject_entry.subject}'"



        print(prompt)

        new_subjects = prompt_lm(prompt)  # Replace with your function that returns suggestions
        perpendicular_subjects = [s for s in new_subjects if s not in graph.body]

        if not perpendicular_subjects:
            continue

        for new_subject in perpendicular_subjects:
            graph.node(new_subject)
            for current_subject in subject_entry.subject:
                graph.edge(current_subject, new_subject)

            for i in range(0, len(perpendicular_subjects), 2):
                if i + 1 < len(perpendicular_subjects):
                    new_axis = (perpendicular_subjects[i], perpendicular_subjects[i + 1])
                    new_subject_entry = subject_entry._replace(subject=new_axis)  # Create new entry
                    subject_queue.append(new_subject_entry)

    
    return graph
# Generate the graph
graph = generate_graph5("emotional dependency", "radical social evolution", max_depth=4)


# Save graph as a text file
with open("concept_graph.txt", "w", encoding="utf-8") as f:
    f.write(str(graph))
"""
# Save graph as a JSON object
graph_json = json.loads(graph.source)
with open("concept_graph.json", "w", encoding="utf-8") as f:
    json.dump(graph_json, f, indent=2)

"""
