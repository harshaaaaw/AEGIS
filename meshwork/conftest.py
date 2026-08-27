import os
import sys

# Make this product's src/ package authoritative when pytest collects this subtree
# (src-layout: the importable package lives at <root>/src/<pkg>, while an
# identically named directory sits at the repo root and would otherwise shadow it).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
