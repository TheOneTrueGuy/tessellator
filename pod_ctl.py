"""Control the RunPod pod: status | spec | stop | start | terminate | deploy | url

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


def spec():
    # Full config dump - enough to recreate the pod if it's terminated.
    r = gql('''query($id: String!) { pod(input: {podId: $id}) {
      name imageName dockerArgs ports env gpuCount vcpuCount memoryInGb
      containerDiskInGb volumeInGb volumeMountPath templateId machineId
      machine { gpuDisplayName }
    } }''', {"id": POD})
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


def deploy():
    # Recreate the ollama pod from the spec captured in DEV.md, on whatever
    # host has capacity. Writes the new pod id to .venv/pod_id.txt.
    # Optional arg: substring to match a different GPU type, e.g. `deploy 4000 Ada`.
    gpu_match = sys.argv[2] if len(sys.argv) > 2 else "2000 Ada"
    r = gql('query { gpuTypes { id displayName } }')
    gpu_id = next((g["id"] for g in r["data"]["gpuTypes"]
                   if gpu_match in g["displayName"]), None)
    if not gpu_id:
        sys.exit(f"no gpuType matching {gpu_match!r}: "
                 f"{[g['displayName'] for g in r['data']['gpuTypes']]}")
    out = gql('''mutation($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) { id machine { gpuDisplayName } }
    }''', {"input": {
        "cloudType": "SECURE", "gpuCount": 1, "gpuTypeId": gpu_id,
        "containerDiskInGb": 40, "volumeInGb": 0,
        "minVcpuCount": 4, "minMemoryInGb": 16,
        "name": "tessellator-ollama", "imageName": "ollama/ollama:latest",
        "dockerArgs": "", "ports": "11434/http",
        "env": [{"key": "OLLAMA_HOST", "value": "0.0.0.0"}],
    }})
    print(json.dumps(out, indent=1))
    pod = out["data"]["podFindAndDeployOnDemand"]
    if pod and pod.get("id"):
        open(".venv/pod_id.txt", "w").write(pod["id"])
        print(f"new pod id -> .venv/pod_id.txt; url: https://{pod['id']}-11434.proxy.runpod.net")


def url():
    print(f"https://{POD}-11434.proxy.runpod.net")


CMDS = {"status": status, "spec": spec, "stop": stop, "start": start, "terminate": terminate, "deploy": deploy, "url": url}
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in CMDS:
        sys.exit(f"usage: pod_ctl.py {'|'.join(CMDS)}")
    CMDS[cmd]()
