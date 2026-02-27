from __future__ import annotations
import json,os,socket
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path

def now():
 return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

@dataclass
class JsonlLogger:

 path:Path
 run_id:str
 app:str="aspectnova-agent"
 app_version:str="0.0.0"

 def emit(self,event,**extra):

  rec={
   "ts":now(),
   "run_id":self.run_id,
   "event":event,
   "host":socket.gethostname(),
   "pid":os.getpid(),
   "app":self.app,
   "app_version":self.app_version
  }

  rec.update(extra)

  self.path.parent.mkdir(parents=True,exist_ok=True)

  with self.path.open("a",encoding="utf8") as f:
   f.write(json.dumps(rec)+"\n")