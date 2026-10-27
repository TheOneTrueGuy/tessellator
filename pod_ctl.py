"""Control the RunPod pod: status | stop | start | terminate | url

Usage: .venv/Scripts/python pod_ctl.py status

Pod id lives in .venv/pod_id.txt, API key in .venv/runpod_key.txt
(neither is committed - both are under .venv/ which is gitignored).
"""

import json
import sys
import urllib.request

KEY = open(".venv/runpod_key.txt").read().strip()
POD = open(".venv/pod_id.txt").read().strip()
API = f"https://api.runpod.io/graphql?api_key={KEY}"


def gql(query, variables=None):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def status():
    r = gql('query($id: String!) { pod(input: {podId: $id}) { desiredStatus costPerHr runtime { ports { privatePort publicPort ip isIpPublic } } } }', {"id": POD})
    print(json.dumps(r["data"]["pod"], indent=1))


def stop():
    # Pod keeps its disk while stopped; you pay storage only (~cents/day), not GPU.
    print(json.dumps(gql('mutation($id: String!) { podStop(input: {podId: $id}) { id desiredStatus } }', {"id": POD})))


def start():
    # Re-uses the saved pod's config/GPU type when resuming.
    print(json.dumps(gql('mutation($id: String!) { podResume(input: {podId: $id}) { id desiredStatus } }', {"id": POD})))


def terminate():
    # Permanent: deletes pod + disk. Redeploy = fresh model downloads.
    print(json.dumps(gql('mutation($id: String!) { podTerminate(input: {podId: $id}) }', {"id": POD})))


def url():
    print(f"https://{POD}-11434.proxy.runpod.net")


CMDS = {"status": status, "stop": stop, "start": start, "terminate": terminate, "url": url}
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in CMDS:
        sys.exit(f"usage: pod_ctl.py {'|'.join(CMDS)}")
    CMDS[cmd]()
