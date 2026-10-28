"""Control the RunPod pod: status | spec | stop | start | terminate | deploy | url

Usage: .venv/Scripts/python pod_ctl.py status

Pod id lives in .venv/pod_id.txt, API key in .venv/runpod_key.txt
(neither is committed - both are under .venv/ which is gitignored).
The Flask app may inject a key/pod at runtime via set_session() - those are
held in memory only, never written to disk.
"""

import json
import os
import sys
import urllib.request

API = "https://api.runpod.io/graphql?api_key={}"

# Runtime-injected credentials (app sessions); CLI falls back to .venv files.
_key = None
_pod = None


def set_session(key=None, pod=None):
    global _key, _pod
    if key:
        _key = key
    if pod:
        _pod = pod


def get_key():
    return _key or open(".venv/runpod_key.txt").read().strip()


def get_pod():
    return _pod or open(".venv/pod_id.txt").read().strip()


def gql(query, variables=None):
    req = urllib.request.Request(
        API.format(get_key()),
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def status():
    r = gql('query($id: String!) { pod(input: {podId: $id}) { desiredStatus costPerHr runtime { ports { privatePort publicPort ip isIpPublic } } } }', {"id": get_pod()})
    print(json.dumps(r["data"]["pod"], indent=1))


def spec():
    # Full config dump - enough to recreate the pod if it's terminated.
    r = gql('''query($id: String!) { pod(input: {podId: $id}) {
      name imageName dockerArgs ports env gpuCount vcpuCount memoryInGb
      containerDiskInGb volumeInGb volumeMountPath templateId machineId
      machine { gpuDisplayName }
    } }''', {"id": get_pod()})
    print(json.dumps(r["data"]["pod"], indent=1))


def stop():
    # Pod keeps its disk while stopped; you pay storage only (~cents/day), not GPU.
    print(json.dumps(gql('mutation($id: String!) { podStop(input: {podId: $id}) { id desiredStatus } }', {"id": get_pod()})))


def start():
    # Re-uses the saved pod's config/GPU type when resuming.
    print(json.dumps(gql('mutation($id: String!) { podResume(input: {podId: $id}) { id desiredStatus } }', {"id": get_pod()})))


def terminate():
    # Permanent: deletes pod + disk. Redeploy = fresh model downloads.
    print(json.dumps(gql('mutation($id: String!) { podTerminate(input: {podId: $id}) }', {"id": get_pod()})))


def deploy(gpu_match=None):
    """Recreate the ollama pod on whatever host has capacity. Returns the pod
    dict {id, machine:{gpuDisplayName}} or None on supply constraint. gpu_match
    defaults to argv[2] (CLI) then "2000 Ada". Writes the id to .venv/pod_id.txt
    when that dir exists."""
    gpu_match = gpu_match or (sys.argv[2] if len(sys.argv) > 2 else "2000 Ada")
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
        "minVcpuCount": 2, "minMemoryInGb": 8,
        "name": "tessellator-ollama", "imageName": "ollama/ollama:latest",
        "dockerArgs": "", "ports": "11434/http",
        "env": [{"key": "OLLAMA_HOST", "value": "0.0.0.0"}],
    }})
    pod = (out.get("data") or {}).get("podFindAndDeployOnDemand")
    if pod and pod.get("id"):
        set_session(pod=pod["id"])
        try:
            os.makedirs(".venv", exist_ok=True)
            open(".venv/pod_id.txt", "w").write(pod["id"])
        except OSError:
            pass
    return pod


def deploy_cli():
    out = deploy()
    print(json.dumps(out, indent=1))
    if out and out.get("id"):
        print(f"new pod id -> .venv/pod_id.txt; url: https://{out['id']}-11434.proxy.runpod.net")


def url():
    print(f"https://{get_pod()}-11434.proxy.runpod.net")


CMDS = {"status": status, "spec": spec, "stop": stop, "start": start, "terminate": terminate, "deploy": deploy_cli, "url": url}
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in CMDS:
        sys.exit(f"usage: pod_ctl.py {'|'.join(CMDS)}")
    CMDS[cmd]()
