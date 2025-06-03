from optimization_framework import SupplyChainState
import pandas as pd
from datetime import datetime

# Create minimal test setup
print("🧪 DEBUGGING ACCLIMATION TIMING")
print("=" * 40)

# Create a simple demand dataframe
demand_data = {i: {1: 100} for i in range(1, 32) if i != 18}  # 100 plants of species 1 needed in polygon 1
demand = pd.DataFrame(demand_data).T.fillna(0)

# Create dummy time matrix
time_data = {i: {j: 1.0 for j in range(1, 32)} for i in range(1, 32)}
time_matrix = pd.DataFrame(time_data)

# Initialize state
state = SupplyChainState(
    start_date=datetime(2025, 9, 1),
    demand=demand,
    time_matrix=time_matrix
)

print(f"Day 0 - Initial state:")
print(f"  Stage 0: {sum(state.acclim_stage_0.values())} plants")
print(f"  Stage 1: {sum(state.acclim_stage_1.values())} plants")
print(f"  Stage 2: {sum(state.acclim_stage_2.values())} plants")
print(f"  Available: {sum(state.available_inventory.values())} plants")

# Simulate ordering 100 plants on day 0
print(f"\n📦 Ordering 100 plants of species 1 on day 0...")
state.acclim_stage_0[1] = 100

print(f"Day 0 - After ordering:")
print(f"  Stage 0: {sum(state.acclim_stage_0.values())} plants")
print(f"  Stage 1: {sum(state.acclim_stage_1.values())} plants")
print(f"  Stage 2: {sum(state.acclim_stage_2.values())} plants")
print(f"  Available: {sum(state.available_inventory.values())} plants")

# Advance through days to see acclimation progression
for day in range(1, 5):
    state.advance_day()
    print(f"\nDay {day} - After advancing:")
    print(f"  Stage 0: {sum(state.acclim_stage_0.values())} plants")
    print(f"  Stage 1: {sum(state.acclim_stage_1.values())} plants") 
    print(f"  Stage 2: {sum(state.acclim_stage_2.values())} plants")
    print(f"  Available: {sum(state.available_inventory.values())} plants")
    
    if sum(state.available_inventory.values()) > 0:
        print(f"  ✅ Plants became available on day {day}!")
        break

print(f"\n🔍 Acclimation timeline:")
print(f"  Day 0: Order placed → Stage 0")
print(f"  Day 1: Stage 0 → Stage 1")
print(f"  Day 2: Stage 1 → Stage 2") 
print(f"  Day 3: Stage 2 → Available")
print(f"  Plants should be available for planting on day 3!") 