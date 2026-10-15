"""Copy tenant graphs from local FalkorDB to the configured FalkorDB Cloud (DUMP/RESTORE)."""
import os, sys, time
import redis
from dotenv import load_dotenv

load_dotenv()
loc = redis.Redis(host="localhost", port=6379)
cl = redis.Redis(host=os.environ["FALKORDB_HOST"], port=int(os.environ["FALKORDB_PORT"]), username=os.environ["FALKORDB_USERNAME"],
                 password=os.environ["FALKORDB_PASSWORD"], socket_timeout=300)
for k in sys.argv[1:]:
    t = time.time()
    blob = loc.dump(k)
    print(k, len(blob) // 1024, "KB dumped", flush=True)
    try:
        cl.restore(k, 0, blob, replace=True)
        print(k, "restored %.1fs" % (time.time() - t), flush=True)
    except Exception as e:
        print(k, "RESTORE FAIL", str(e)[:200])
print(cl.execute_command("GRAPH.LIST"), cl.info("memory")["used_memory_human"], cl.info("memory").get("maxmemory_human"))
