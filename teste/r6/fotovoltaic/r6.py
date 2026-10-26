import sys; sys.path.insert(0, "/home/claude/sm/teste/r6/fotovoltaic")
from ruleaza import ruleaza
from fraze_r6 import FRAZE
ruleaza(FRAZE, "f", png=set(range(1, 49)))
