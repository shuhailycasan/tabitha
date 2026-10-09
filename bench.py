"""Benchmark the chat loop against sample_grades.xlsx. Usage: python bench.py  (server must be running)."""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import subprocess
import urllib.request

BASE = "http://localhost:8777"
THINK = "fast" not in sys.argv  # python bench.py fast  -> thinking off
CASES = [  # (question, substrings that must all appear in the reply)
    ("How many students are there?", ["15"]),
    ("Who has the highest average grade across all subjects?", ["Cora", "87.33"]),
    ("What is the average Math score?", ["75.7"]),
    ("Which student has the most days absent?", ["Gia", "15"]),
    ("How is Liam doing overall?", ["74", "88", "91"]),
    ("Which students scored above 90 in Science?", ["Ben", "Dan", "Gia", "Ivy", "Kim", "Liam"]),
]


def run(case):
    q, must = case
    t0, rounds, think, tools, reply = time.time(), 0, 0, [], ""
    body = json.dumps({"dataset_id": DS, "request_id": f"bench{time.time_ns()}", "think": THINK, "messages": [{"role": "user", "content": q}]}).encode()
    req = urllib.request.Request(f"{BASE}/api/chat", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        lines = [l.decode() for l in r]
    for line in lines:
        e = json.loads(line) if line.strip() else {}
        t = e.get("type")
        if t == "status": rounds += 1
        elif t == "think": think += 1
        elif t == "tool": tools.append(e["tool"] + ("" if e["ok"] else "!ERR"))
        elif t == "done": reply = e["reply"]
        elif t == "error": reply = "ERROR " + e["error"]
    ok = all(m.lower() in reply.lower() for m in must)
    return dict(q=q, ok=ok, secs=round(time.time() - t0), rounds=rounds, think=think, tools=tools, reply=reply[:150])


if __name__ == "__main__":
    DS = json.loads(subprocess.check_output(["curl", "-s", "-F", "file=@sample_grades.xlsx", f"{BASE}/api/upload"]))["id"]
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(run, CASES))
    for x in res:
        print(("PASS" if x["ok"] else "FAIL"), f'{x["secs"]}s rounds={x["rounds"]} think={x["think"]} tools={x["tools"]}\n   Q: {x["q"]}\n   A: {x["reply"]}')
    print(f'\n{sum(x["ok"] for x in res)}/{len(res)} correct | avg {sum(x["secs"] for x in res)//len(res)}s | avg think tokens {sum(x["think"] for x in res)//len(res)} | avg rounds {sum(x["rounds"] for x in res)/len(res):.1f}')
