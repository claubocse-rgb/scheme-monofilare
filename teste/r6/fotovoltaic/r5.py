import sys, json; sys.path.insert(0, "/home/claude/sm/teste/r6/fotovoltaic")
from ruleaza import ruleaza
F = [o["fraza"] for o in json.load(open("/home/claude/sm/teste/r5/fotovoltaic/fraze.json"))]
ruleaza(F, "r5_", png={3,11,13,16,28,31})
