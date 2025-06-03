import json
import pandas as pd

# Load the simulation data
with open('reforestation_daily_data.json', 'r') as f:
    data = json.load(f)

print("🔍 INVENTORY DISCREPANCY INVESTIGATION")
print("=" * 60)

# Extract data
daily_data = data['daily_data']
project_summary = data['project_summary']

# Get the last day's data as final state
final_day_key = str(max(int(k) for k in daily_data.keys()))
final_state = daily_data[final_day_key]

print(f"📊 PROJECT SUMMARY:")
print(f"Total days: {project_summary['total_days']}")
print(f"Initial demand: {project_summary['initial_demand']:,}")
print(f"Final completion: {project_summary['final_completion']:.1f}%")
print(f"Total cost: ${project_summary['total_cost']:,.2f}")

print(f"\n🏭 FINAL WAREHOUSE STATE (Day {final_day_key}):")
available = final_state.get('warehouse_inventory_by_species', {})
stage_0 = final_state.get('acclim_stage_0', {})
stage_1 = final_state.get('acclim_stage_1', {})
stage_2 = final_state.get('acclim_stage_2', {})

total_available = sum(int(v) for v in available.values())
total_stage_0 = sum(int(v) for v in stage_0.values())
total_stage_1 = sum(int(v) for v in stage_1.values())
total_stage_2 = sum(int(v) for v in stage_2.values())

print(f"Available inventory: {total_available:,}")
print(f"Acclimation stage 0: {total_stage_0:,}")
print(f"Acclimation stage 1: {total_stage_1:,}")
print(f"Acclimation stage 2: {total_stage_2:,}")

total_final_inventory = total_available + total_stage_0 + total_stage_1 + total_stage_2
print(f"Total final inventory: {total_final_inventory:,}")

# Calculate total orders and total planted across all days
total_orders_by_species = {str(i): 0 for i in range(1, 11)}
total_planted_by_species = {str(i): 0 for i in range(1, 11)}

print(f"\n📈 CALCULATING TOTALS ACROSS ALL DAYS...")

for day_key, day_data in daily_data.items():
    # Sum up orders placed this day
    orders_placed = day_data.get('orders_placed', [])
    for order in orders_placed:
        species_breakdown = order.get('species_breakdown', {})
        for species_id, quantity in species_breakdown.items():
            total_orders_by_species[str(species_id)] += quantity
    
    # Sum up plants planted this day
    planting_activities = day_data.get('planting_activities', [])
    for activity in planting_activities:
        species_id = str(activity.get('species_id', 0))
        quantity = activity.get('quantity', 0)
        if species_id != '0':
            total_planted_by_species[species_id] += quantity

total_ordered = sum(total_orders_by_species.values())
total_planted = sum(total_planted_by_species.values())

print(f"\n🧮 ACCOUNTING CHECK:")
print(f"Total ordered across all days: {total_ordered:,}")
print(f"Total planted across all days: {total_planted:,}")
print(f"Calculated remaining: {total_ordered - total_planted:,}")
print(f"Actual final inventory: {total_final_inventory:,}")
print(f"DISCREPANCY: {(total_ordered - total_planted) - total_final_inventory:,} plants are missing!")

print(f"\n📋 DETAILED BREAKDOWN BY SPECIES:")
print("-" * 50)
for species_id in range(1, 11):
    species_str = str(species_id)
    ordered = total_orders_by_species[species_str]
    planted = total_planted_by_species[species_str]
    
    # Final inventory for this species
    avail = int(available.get(species_str, 0))
    s0 = int(stage_0.get(species_str, 0))
    s1 = int(stage_1.get(species_str, 0))
    s2 = int(stage_2.get(species_str, 0))
    final_species_inventory = avail + s0 + s1 + s2
    
    remaining_calculated = ordered - planted
    discrepancy = remaining_calculated - final_species_inventory
    
    print(f"Species {species_id}:")
    print(f"  Ordered: {ordered:,}, Planted: {planted:,}")
    print(f"  Calculated remaining: {remaining_calculated:,}")
    print(f"  Final inventory: {final_species_inventory:,} (avail:{avail}, s0:{s0}, s1:{s1}, s2:{s2})")
    print(f"  DISCREPANCY: {discrepancy:,}")
    print()

# Check if demand was properly reduced
print(f"🎯 DEMAND ANALYSIS:")
print(f"Initial demand: {project_summary['initial_demand']:,}")
print(f"Final remaining demand: {final_state.get('remaining_demand_total', 0):,}")
print(f"Total demand satisfied: {project_summary['initial_demand'] - final_state.get('remaining_demand_total', 0):,}")
print(f"Total plants planted: {total_planted:,}")
print(f"Demand vs planted discrepancy: {(project_summary['initial_demand'] - final_state.get('remaining_demand_total', 0)) - total_planted:,}")

# Let's check some daily progression to see where plants might be getting lost
print(f"\n📈 WAREHOUSE PROGRESSION (Last 10 days):")
print("-" * 60)

last_days = sorted([int(k) for k in daily_data.keys()])[-10:]
for day_num in last_days:
    day_data = daily_data[str(day_num)]
    warehouse_total = day_data.get('warehouse_inventory_total', 0)
    remaining_demand = day_data.get('remaining_demand_total', 0)
    plants_planted_today = day_data.get('total_plants_planted_today', 0)
    
    print(f"Day {day_num}: Warehouse: {warehouse_total:,}, Demand: {remaining_demand:,}, Planted: {plants_planted_today:,}")

print(f"\n🔍 POSSIBLE CAUSES FOR DISCREPANCY:")
print("-" * 50)
print("1. Plants might be getting 'consumed' during transportation without being counted as planted")
print("2. There might be an inventory leak in the acclimation stage advancement")  
print("3. Orders might be double-counted or planted amounts under-counted")
print("4. Warehouse capacity limits might be causing plant loss") 