"""
run_backend.py
Run this to see backend output.
Usage: python run_backend.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analytics.pipeline import run_pipeline

print("=" * 60)
print("DiseaseWatch Backend — running pipeline...")
print("=" * 60)

data = run_pipeline()

print(f"\nDiseases loaded: {sorted(set(r['disease'] for r in data['records']))}")
print(f"Total records: {len(data['records'])}")
print(f"Countries with COVID data: {len(data['covid_map'])}")
print(f"Global threat score: {data['global_threat']['score']} / 100 ({data['global_threat']['level']})")
print(f"ProMED alerts: {len(data['promed_alerts'])}")
print(f"What changed today: {len(data['what_changed'])} events")
print(f"Data confidence: {data['confidence']['score']}%")
print(f"Fetched at: {data['fetched_at']}")
print("\nTop 5 changes:")
for c in data['what_changed'][:5]:
    print(f"  {c['disease']} in {c['country']}: {c['velocity']:+.1f}%")
print("\nBackend pipeline complete.")