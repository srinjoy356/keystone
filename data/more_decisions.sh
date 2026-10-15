export PYTHONPATH=. PYTHONIOENCODING=utf-8 DECISION_LIMIT=1000
P=.venv/Scripts/python
$P -u -m keystone.decisions FalkorDB/FalkorDB FalkorDB/falkordb-browser FalkorDB/QueryWeaver FalkorDB/docs FalkorDB/GraphRAG-SDK FalkorDB/falkordb-py
$P -u -m keystone.decisions --issues FalkorDB/FalkorDB FalkorDB/GraphRAG-SDK FalkorDB/falkordb-py
echo ALLDONE
